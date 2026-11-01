"""The writes of the implement job (#2665): the run of one Staged item from its first task group
to a ready pull request, and the stop of an item that cannot get there.

**Where it runs.** The job runs a step only when `roadmap.implement.in_runner` is true. The
step's shell checks the first word of a command and is no security boundary, so the pod of a
runner Job is the sandbox. The job clears the dumpable flag of its own process, so that the shell,
a child of the same user, cannot read the job's environment (#2667). Every `git` command, every
GitHub call and every `gh` call of the job runs in this process, never in the agent's shell. The
process runner gives a `git` or `gh` child the session's token, and any other child (`uv`,
`ruff`) none. A `git` or `gh` child holds that token in its environment while it runs, so the job
ends every process of a step when the step ends (`end_leftover_processes`), before such a child
can start.

**One item.** The job takes over the staged branch in a worktree, sets Status In Progress and
rebases onto the fetched default branch. It runs one step for each group that has an unticked
task, regenerates the documentation, archives the change, rebases again and pushes with a lease.
Then it sets the title and the body of the pull request, comments the outcome of each step, and
watches the checks. A failed check gets one fix step. When the checks pass the job marks the pull
request ready and sets Status In Review. It never merges.

**A Planned item** (#2714) has its plan on the default branch and no branch. The job makes the
branch `<type>/<issue>-<slug>` at the fetched default branch, and goes on as above. A pull request
needs a commit past its base, so the job publishes the branch at its first push (`_publish`): it
pushes with `-u`, opens the draft, and records `implement.branch` and `implement.pr`. A stop before
the first commit pushes nothing. A stop after it publishes what passed, so a retry finds the branch
and the draft and takes them over as a Staged item.

**A stop.** A step that stops, a conflict, a failed command or a check that fails twice stops the
item: the job pushes the commits that passed, comments the step, the reason and the last message
of the agent, sets Status Blocked, and records `implement.stopped`. It does not run the item again
until a clear rule of the Service removes the stop: a person's comment `implement: retry`, or a new
runner image (`stop_clear.py`).

**A claim** (#2910). The Service holds the item with `owner/service` while the Job runs. The job
reads the item before each unticked task group, when a step stops, and before the push. When an
agent or a person holds it by then, the job ends the item at once: it pushes nothing, opens no
pull request, comments why, and changes neither the Status nor the owner. The groups that passed stay in the
worktree, which the job removes; the new owner starts from the branch on `origin`.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, NamedTuple

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.config.commands import BIN_DEVOPS, BIN_GIT, BIN_UV
from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
    CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import acts_as_github_app, run_subprocess
from devops_cli.core.process_hardening import adopt_orphans, deny_environment_reads
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubUnauthenticatedError,
    GitOperationError,
    RoadmapImplementError,
)
from devops_cli.git.worktree_add import add_worktree
from devops_cli.github.check_verdict import PRCheckItem
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.implement import GIT_OPERATION, ImplementPlan, ImplementTarget
from devops_cli.roadmap.implement_hooks import install_hook_environments, trusted_config
from devops_cli.roadmap.implement_pull import WatchKind, failed_log, mark_ready, watch_pull
from devops_cli.roadmap.implement_scoped_ci import (
    ScopedResult,
    plan_tests,
    run_scoped_checks,
    scoped_checks,
)
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    find_change,
    run_fix_step,
    run_step,
    section_text,
)
from devops_cli.roadmap.pull_labels import declared_labels
from devops_cli.roadmap.stage_change import closing_keyword_in, delivery_title, safe_text
from devops_cli.roadmap.status_sync import StatusFacts, derive_status
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.store import ImplementRecordKey, Item, ItemField, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

_TIMEOUT = CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS
_WHY_HEADINGS = frozenset({"why"})


class _Mark(NamedTuple):
    """How many outcomes, scoped runs and notes the item had at one moment (#3043)."""

    outcomes: int
    scoped: int
    notes: int


_NOTHING_YET = _Mark(0, 0, 0)


class _StopError(Exception):
    """An item stops: the job's own signal, caught where the item's run ends. `push` says whether
    the commits that passed are worth pushing. `diff` is the diff of the work that a stopped step
    discarded, and `diff_cut` says that it was cut (#2721)."""

    def __init__(
        self,
        step: str,
        reason: str,
        last_message: str = "",
        *,
        push: bool = True,
        diff: str = "",
        diff_cut: bool = False,
    ) -> None:
        super().__init__(reason)
        self.step = step
        self.reason = reason
        self.last_message = last_message
        self.push = push
        self.diff = diff
        self.diff_cut = diff_cut


class _ClaimedError(Exception):
    """An agent or a person claimed the item: the job's own signal that the run ends at the next
    group boundary, caught where the item's run ends. `owner` is the claim in lower case and
    `boundary` says where the run ended."""

    def __init__(self, owner: str, boundary: str) -> None:
        super().__init__(owner)
        self.owner = owner
        self.boundary = boundary


class _Ended(StrEnum):
    """How the run of an item ended."""

    READY = "ready"
    STOPPED = "stopped"
    YIELDED = "yielded"


@dataclass(frozen=True)
class ImplementFailure:
    """An item whose run failed in a way that left it alone: the class of the error and why."""

    number: int
    title: str
    error: str
    reason: str = ""


@dataclass(frozen=True)
class ImplementApplied:
    """What a run did: the items it took to a ready pull request, the items it stopped, the items
    it ended because an agent or a person claimed them (#2910), and the items whose stop or finish
    could not be written."""

    ready: tuple[int, ...] = ()
    stopped: tuple[int, ...] = ()
    failed: tuple[ImplementFailure, ...] = ()
    yielded: tuple[int, ...] = ()


def _stopped_by(step: str, outcome: StepOutcome) -> _StopError:
    """The stop of an item for a step that stopped, with the diff of its discarded work."""
    return _StopError(
        step, outcome.reason, outcome.last_message, diff=outcome.diff, diff_cut=outcome.diff_cut
    )


def _diff_section(stop: _StopError) -> str:
    """The diff of the discarded work of a stopped step as a fenced block of the stop comment, or
    nothing when there is none. The diff is text of the agent, so it is masked here again, at the
    point where it leaves for GitHub. The fence is `code_fence` of the diff."""
    if not stop.diff:
        return ""
    texts = MESSAGES.roadmap
    diff = mask_secrets(stop.diff).rstrip("\n")
    cut = texts.implement_comment_diff_cut.format(limit=CONST_ROADMAP_IMPLEMENT_DIFF_CHARS)
    return texts.implement_comment_diff.format(
        cut=cut if stop.diff_cut else "", fence=code_fence(diff), diff=diff
    )


def require_runner(repo: str) -> None:
    """Raise `RoadmapImplementError` unless the process is a runner Job for `repo`:
    `roadmap.implement.in_runner` is true, the process acts as the GitHub App, and its token is
    limited to `repo` by `service.github_app.token_repository`. A Job that `devops k8s run-job`
    makes sets no such repository, and its token would cover the whole installation (#2667). The
    job calls this before it reads a repository or asks a model."""
    settings = load_settings()
    texts = MESSAGES.roadmap
    if not settings.roadmap.implement.in_runner:
        raise RoadmapImplementError(texts.implement_job_runner_refused)
    if not acts_as_github_app():
        raise RoadmapImplementError(texts.implement_job_token_not_app)
    scoped = settings.service.github_app.token_repository
    if (scoped or "").casefold() != repo.casefold():
        raise RoadmapImplementError(
            texts.implement_job_token_scope_refused.format(repo=repo, scoped=scoped or "unset")
        )


def _tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES:])


def _step_label(group: int) -> str:
    return MESSAGES.roadmap.implement_step_group.format(group=group)


@contextmanager
def _worktree(source: Path, target: ImplementTarget) -> Iterator[Path]:
    """The worktree on the staged branch, taken over from `origin`, or for a Planned item on the new
    branch at the fetched default branch. The worktree and the local branch go when the block
    ends, so the clone keeps its HEAD and holds no issue."""
    parts = target.new_branch
    report = add_worktree(
        source,
        issue=target.item.number,
        type_=parts.type if parts else None,
        slug=parts.slug if parts else None,
    )
    path = Path(report.path)
    try:
        yield path
    finally:
        git(source, "worktree", "remove", "--force", str(path), operation=GIT_OPERATION)
        git(source, "branch", "-D", target.branch, operation=GIT_OPERATION)


@dataclass
class _ItemRun:
    """The run of one item in its worktree."""

    store: RoadmapStore
    repo: str
    path: Path
    target: ImplementTarget
    model: Any
    window: int
    default: str
    step: str = ""
    change: str = ""
    outcomes: list[StepOutcome] = field(default_factory=list)
    # Every run of a scoped check (#3043), in order, the failed runs too, and the notes that say why
    # the tests check was narrower than the changed files.
    scoped: list[ScopedResult] = field(default_factory=list)
    scoped_notes: list[str] = field(default_factory=list)
    # The draft pull request: the target's, or for a Planned item the one `_publish` opens.
    pull: int | None = field(init=False)

    def __post_init__(self) -> None:
        self.pull = self.target.pull

    # ── Small helpers ──

    @property
    def number(self) -> int:
        return self.target.item.number

    @property
    def branch(self) -> str:
        return self.target.branch

    def _git(self, *args: str) -> str:
        return git(self.path, *args, operation=GIT_OPERATION)

    def _head(self) -> str:
        return self._git("rev-parse", "HEAD")

    def _fresh(self) -> Item:
        """The item as it is now: a field write refuses an item read before an earlier write."""
        held = self.store.item(self.number)
        if held is None:
            raise RoadmapImplementError(MESSAGES.roadmap.item_left_not_item)
        return held

    def _spend(self) -> str:
        return json.dumps(
            {
                "requests": sum(o.requests for o in self.outcomes),
                "input_tokens": sum(o.input_tokens for o in self.outcomes),
                "output_tokens": sum(o.output_tokens for o in self.outcomes),
            }
        )

    def _record(self, **marks: str) -> None:
        keys = {
            "group": ImplementRecordKey.GROUP,
            "sha": ImplementRecordKey.SHA,
            "spend": ImplementRecordKey.SPEND,
        }
        self.store.set_marks(self._fresh(), {keys[name]: value for name, value in marks.items()})

    def _program(self, argv: Sequence[str]) -> None:
        """Run a command of the project in the worktree, outside any agent shell. Raises
        `_StopError` for the current step when it fails or runs out of time."""
        shown = " ".join(argv)
        texts = MESSAGES.roadmap
        try:
            done = run_subprocess(list(argv), cwd=self.path, quiet=True, timeout=_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            reason = texts.implement_stop_program_timeout.format(command=shown, seconds=_TIMEOUT)
            raise _StopError(self.step, reason) from exc
        if done.returncode != 0:
            output = _tail(f"{done.stdout or ''}{done.stderr or ''}")
            reason = texts.implement_stop_program_failed.format(
                command=shown, status=done.returncode, output=output
            )
            raise _StopError(self.step, reason)

    def _commit_if_changed(self, message: str) -> None:
        self._git("add", "-A")
        if self._git("status", "--porcelain"):
            self._git("commit", "-q", "-m", message)

    def _active_change(self) -> Path | None:
        """The change folder of the item in the worktree, or None once it is archived."""
        folder = self.path / CONST_OPENSPEC_CHANGES_DIR
        if not any(folder.glob(f"{self.number}-*")):
            return None
        return find_change(self.path, self.number)

    # ── The sequence ──

    def execute(self) -> None:
        """Run the item from the first step to a ready pull request. Raises `_StopError`."""
        self._start()
        self._groups()
        self._finish_change()
        self._require_unclaimed(MESSAGES.roadmap.implement_boundary_end)
        pull = self._push()
        self._pull_request(pull)
        self._checks(pull)
        self._ready(pull)

    def _start(self) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["rebase"]
        marks: dict[Any, str | None] = {ImplementRecordKey.BRANCH: self.branch}
        if self.pull is not None:
            marks[ImplementRecordKey.PR] = str(self.pull)
        if self.target.retry:
            marks[ImplementRecordKey.STOPPED] = None
        self.store.set_field(
            self._fresh(), ItemField.STATUS, CONST_ROADMAP_STATUS_IN_PROGRESS, marks=marks
        )
        self._sync(push_on_conflict=False)
        self._install_hooks()

    def _hooks_config(self) -> Path | None:
        """The configuration of the hooks as the default branch has it, or None when it has none.
        Every hook run reads this copy, never the file of the checkout, which the agent can edit
        (#3043)."""
        return trusted_config(self.path, f"origin/{self.default}")

    def _install_hooks(self) -> None:
        """Fetch the hook environments before the first model request, so that no network failure
        wastes a step. A failure stops the item with nothing to push (#3043)."""
        self.step = MESSAGES.roadmap.implement_step_names["hooks"]
        config = self._hooks_config()
        failure = install_hook_environments(self.path, config) if config else None
        if failure is not None:
            raise _StopError(self.step, failure, push=False)

    def _sync(self, *, push_on_conflict: bool = True) -> None:
        """Fetch the default branch and rebase onto it. A conflict aborts the rebase, which puts the
        branch back on its tip, and stops the item. The stop pushes the commits that passed, unless
        `push_on_conflict` is false: at the start of the run there is nothing new to push."""
        self._git("fetch", "-q", "origin", self.default)
        try:
            self._git("rebase", f"origin/{self.default}")
        except GitOperationError as exc:
            aborted = run_subprocess(
                [BIN_GIT, "-C", str(self.path), "rebase", "--abort"],
                check=False,
                quiet=True,
                timeout=_TIMEOUT,
            )
            texts = MESSAGES.roadmap
            reason = texts.implement_stop_rebase.format(branch=self.default, output=str(exc))
            if aborted.returncode != 0:
                reason += texts.implement_stop_abort_failed.format(output=_tail(aborted.stderr))
            raise _StopError(self.step, reason, push=push_on_conflict) from exc

    def _require_unclaimed(self, boundary: str) -> None:
        """Raise `_ClaimedError` when an agent or a person holds the item now (#2910). The
        Service's own claim holds nothing against the job."""
        owner = claimed_by(self._fresh())
        if owner is not None:
            raise _ClaimedError(owner, boundary)

    def _groups(self) -> None:
        change = self._active_change()
        if change is None:
            return
        self.change = change.name
        tasks = parse_task_groups((change / "tasks.md").read_text(encoding="utf-8"))
        for group in tasks:
            if all(task.ticked for task in group.tasks):
                continue
            self.step = _step_label(group.number)
            self._require_unclaimed(
                MESSAGES.roadmap.implement_boundary_group.format(group=group.number)
            )
            outcome = run_step(
                self.store,
                item=self.number,
                group=group.number,
                source=self.path,
                model=self.model,
                window=self.window,
                hooks=self._hooks_config(),
            )
            self.outcomes.append(outcome)
            if outcome.status is StepStatus.STOPPED:
                raise _stopped_by(self.step, outcome)
            self._record(group=str(group.number), sha=outcome.commit)

    def _generate_docs(self) -> None:
        """Generate the documents and commit what changed."""
        self.step = MESSAGES.roadmap.implement_step_names["docs"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "docs", "generate", "--sync-readme"])
        self._commit_if_changed(f"docs: regenerate the documentation (#{self.number})")

    def _finish_change(self) -> None:
        names = MESSAGES.roadmap.implement_step_names
        self._generate_docs()
        change = self._active_change()
        if change is None:
            return
        self.step = names["archive"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "openspec", "archive", change.name])
        self._commit_if_changed(f"docs(openspec): archive the change (#{self.number})")

    def _push(self) -> int:
        """Rebase onto the default branch again, then push with a lease on the remote tip that the
        job has seen, so a push of anyone else is never overwritten. A Planned item has no remote
        tip yet: its first push publishes the branch. The number of the pull request."""
        self.step = MESSAGES.roadmap.implement_step_names["push"]
        self._sync()
        self._scoped_checks()
        self.step = MESSAGES.roadmap.implement_step_names["push"]
        if self.pull is None:
            return self._publish()
        self._push_with_lease()
        return self.pull

    def _scoped_run(self) -> ScopedResult | None:
        """Run the scoped checks for the paths the item changed, and keep their results for the
        comment. The first failed result, or None when every check passed."""
        listed = self._git(
            "diff", "--name-only", "--diff-filter=ACMR", "-z", f"origin/{self.default}", "HEAD"
        )
        changed = [name for name in listed.split("\0") if name]
        tests = plan_tests(self.path, changed)
        if tests.note and tests.note not in self.scoped_notes:
            self.scoped_notes.append(tests.note)
        checks = scoped_checks(self.default, tests.paths, config=self._hooks_config())
        results = run_scoped_checks(self.path, checks)
        self.scoped.extend(results)
        return next((result for result in results if not result.passed), None)

    def _scoped_checks(self) -> None:
        """Run the checks a person runs before a push (#3043), and give a failed check to a fix
        step, at most `roadmap.implement.repair_rounds` times. The documents are generated again
        after each fix, because a fix can change a command or an option. The job pushes only a head
        that passed them, so any stop in this phase pushes nothing, an error or a command that ran
        out of time too. Raises `_StopError`."""
        try:
            self._scoped_rounds()
        except _StopError as stop:
            stop.push = False
            raise
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError, subprocess.TimeoutExpired) as exc:
            raise _error_stop(self.step, exc, push=False) from exc

    def _scoped_rounds(self) -> None:
        """The runs of the scoped checks, and the fix step after each failed run."""
        names = MESSAGES.roadmap.implement_step_names
        budget = load_settings().roadmap.implement.repair_rounds
        for used in range(budget + 1):
            self.step = names["scoped"]
            failed = self._scoped_run()
            if failed is None:
                return
            if used == budget:
                reason = MESSAGES.roadmap.implement_stop_scoped_failed.format(
                    name=failed.name, rounds=budget, command=failed.command, output=failed.log
                )
                raise _StopError(self.step, reason)
            self._fix(failed.name, failed.log)
            self._generate_docs()

    def _push_with_lease(self) -> None:
        remote = self._git("rev-parse", f"origin/{self.branch}")
        if remote != self._head():
            self._git("push", f"--force-with-lease={self.branch}:{remote}", "origin", self.branch)

    def _has_new_commits(self) -> bool:
        return self._head() != self._git("rev-parse", f"origin/{self.default}")

    def _publish(self) -> int:
        """The first push of a Planned item: push the new branch with `-u`, open its draft pull
        request, and record both. The first body closes no issue: the body that does comes after
        the archive. A draft that GitHub refuses takes the branch off `origin` again, so no branch
        stays without a pull request, and stops the item with nothing left to push."""
        texts = MESSAGES.roadmap
        self._git("push", "-u", "origin", self.branch)
        try:
            created = get_github_session().client.create_draft_pull(
                self.repo,
                title=self._delivery_title(),
                body=texts.implement_pull_body_draft.format(number=self.number),
                head=self.branch,
                base=self.default,
            )
        except DevOpsCLIError as exc:
            self._git("push", "origin", "--delete", self.branch)
            reason = texts.implement_stop_draft_failed.format(
                branch=self.branch, output=mask_secrets(str(exc))
            )
            raise _StopError(self.step, reason, push=False) from exc
        self.pull = created.number
        self.store.set_marks(self._fresh(), {ImplementRecordKey.PR: str(created.number)})
        return created.number

    def _delivery_title(self) -> str:
        """The title of the pull request: the title of the issue, with a scope that
        `.github/labels.yml` declares on the default branch and no other (#2800)."""
        declared = declared_labels(self.store, ref=None)
        return delivery_title(self.target.item.title, declared)

    def _archived_name(self) -> str:
        """The folder `openspec archive` made for the change: `<date>-<issue>-<slug>`."""
        folder = self.path / CONST_OPENSPEC_ARCHIVE_DIR
        pattern = f"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-{self.number}-*"
        return next((p.name for p in sorted(folder.glob(pattern)) if p.is_dir()), "")

    def _why(self, archived: str) -> str:
        """The "why" of the proposal on one line, at most `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`
        long. The title of the item stands in when the proposal has none, or when its text holds a
        closing keyword for an issue, which would close that issue when the pull request merges."""
        proposal = self.path / CONST_OPENSPEC_ARCHIVE_DIR / archived / "proposal.md"
        text = ""
        if proposal.is_file():
            section = section_text(proposal.read_text(encoding="utf-8"), _WHY_HEADINGS)
            text = safe_text(section.partition("\n")[2])
        if not text or closing_keyword_in(text) is not None:
            text = safe_text(self.target.item.title)
        return textwrap.shorten(text, CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS, placeholder="...")

    def _pull_request(self, pull: int) -> None:
        """Set the title and the body of the pull request. The title is the one of the issue: the
        staging pull request of a Staged item has the type `docs(openspec)` (#2714)."""
        self.step = MESSAGES.roadmap.implement_step_names["pull_request"]
        texts = MESSAGES.roadmap
        archived = self._archived_name()
        body = texts.implement_pull_body.format(
            number=self.number, why=self._why(archived), archived=archived
        )
        client = get_github_session().client
        client.update_pull(self.repo, pull, title=self._delivery_title(), body=body)
        self._comment(pull, _NOTHING_YET)

    def _mark(self) -> _Mark:
        """How many outcomes, scoped runs and notes there are now, for `_comment`."""
        return _Mark(len(self.outcomes), len(self.scoped), len(self.scoped_notes))

    def _comment(self, pull: int, since: _Mark) -> None:
        """Comment on the pull request with the steps, the scoped runs and the notes that came
        after `since`: the repair rounds are in the trace (#3043)."""
        texts = MESSAGES.roadmap
        lines = [
            *(self._outcome_line(outcome) for outcome in self.outcomes[since.outcomes :]),
            *self._scoped_lines(since),
        ]
        comment = texts.implement_pull_comment.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, lines="\n".join(lines) or "-"
        )
        get_github_session().client.comment_on_pull(self.repo, pull, comment)

    def _scoped_lines(self, since: _Mark) -> list[str]:
        """One line for each run of a scoped check after `since`: its name, its result and its
        seconds. Then one line for each note on the tests check."""
        texts = MESSAGES.roadmap
        runs = [
            texts.implement_pull_comment_scoped.format(
                name=result.name,
                result=texts.implement_scoped_passed
                if result.passed
                else texts.implement_scoped_failed,
                seconds=result.seconds,
            )
            for result in self.scoped[since.scoped :]
        ]
        notes = [
            texts.implement_pull_comment_scoped_note.format(note=note)
            for note in self.scoped_notes[since.notes :]
        ]
        return [*runs, *notes]

    def _outcome_line(self, outcome: StepOutcome) -> str:
        texts = MESSAGES.roadmap
        commit = texts.implement_pull_comment_commit.format(commit=outcome.commit[:12])
        return texts.implement_pull_comment_line.format(
            step=_step_label(outcome.group) if outcome.group else texts.implement_step_fix,
            title=outcome.title,
            status=outcome.status.value,
            requests=outcome.requests,
            rounds=outcome.repair_rounds,
            commit=commit if outcome.commit else "",
        )

    def _checks(self, pull: int) -> None:
        """Watch the checks. A failed check gets a fix step, a push and a new watch, at most
        `roadmap.implement.repair_rounds` times (#3043). A check that still fails after the last
        round stops the item."""
        self.step = MESSAGES.roadmap.implement_step_names["checks"]
        budget = load_settings().roadmap.implement.repair_rounds
        watch = watch_pull(self.repo, pull, self._head())
        for _round in range(budget):
            if watch.kind is not WatchKind.FAILED or watch.check is None:
                break
            self._repair_after_push(pull, watch.check)
            watch = watch_pull(self.repo, pull, self._head())
        if watch.kind is not WatchKind.READY:
            raise _StopError(self.step, watch.reason)

    def _repair_after_push(self, pull: int, check: PRCheckItem) -> None:
        """One repair round for the failed check `check` of the pull request: a fix step, the push
        (with the scoped checks), and a comment that shows the round."""
        since = self._mark()
        self._fix(check.name, failed_log(self.repo, check))
        self._push()
        self._comment(pull, since)
        self.step = MESSAGES.roadmap.implement_step_names["checks"]

    def _fix(self, check: str, log: str) -> None:
        self.step = MESSAGES.roadmap.implement_step_fix
        outcome = run_fix_step(
            self.store,
            item=self.number,
            fix=FixRequest(check=check, log=log),
            source=self.path,
            model=self.model,
            window=self.window,
            hooks=self._hooks_config(),
        )
        self.outcomes.append(outcome)
        if outcome.status is StepStatus.STOPPED:
            raise _stopped_by(self.step, outcome)

    def _ready(self, pull: int) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["ready"]
        mark_ready(self.repo, pull)
        head = self._head()
        marks: dict[Any, str | None] = {
            ImplementRecordKey.SHA: head,
            ImplementRecordKey.PR: str(pull),
            ImplementRecordKey.SPEND: self._spend(),
        }
        self.store.set_field(
            self._fresh(), ItemField.STATUS, CONST_ROADMAP_STATUS_IN_REVIEW, marks=marks
        )
        spend = json.loads(self._spend())
        self.store.comment(
            self.number,
            MESSAGES.roadmap.implement_comment_finished.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, pull=pull, **spend
            ),
        )

    # ── The end for a claim ──

    def yield_to(self, claimed: _ClaimedError) -> None:
        """Tell the item why the run ended. Nothing is pushed and no pull request is opened, and
        the Status and the owner stay as the new owner has them."""
        self.store.comment(
            self.number,
            MESSAGES.roadmap.implement_comment_claimed.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
                owner=claimed.owner,
                boundary=claimed.boundary,
            ),
        )

    def end_stopped(self, stop: _StopError) -> _Ended:
        """End a run that a step stopped. A claim that came while the step ran is the end of the
        run at this boundary: the stop pushes nothing then, opens no pull request and sets no
        Status (#2910)."""
        try:
            self._require_unclaimed(MESSAGES.roadmap.implement_boundary_stop.format(step=stop.step))
        except _ClaimedError as claimed:
            self.yield_to(claimed)
            return _Ended.YIELDED
        self.stop(stop)
        return _Ended.STOPPED

    # ── The stop ──

    def stop(self, stop: _StopError) -> None:
        """Push what passed, tell the item why, set it Blocked, and record the step."""
        texts = MESSAGES.roadmap
        note = self._push_passed() if stop.push else ""
        last = safe_text(mask_secrets(stop.last_message))[
            :CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS
        ]
        reason = textwrap.indent(
            mask_secrets(stop.reason).strip()[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS], "    "
        )
        self.store.comment(
            self.number,
            texts.implement_comment_stopped.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
                step=stop.step,
                reason=reason,
                last=last or texts.implement_comment_last_none,
                diff=_diff_section(stop),
                note=note,
            ),
        )
        marks: dict[Any, str | None] = {
            ImplementRecordKey.STOPPED: stop.step,
            ImplementRecordKey.SPEND: self._spend(),
        }
        if self.pull is not None:
            marks[ImplementRecordKey.PR] = str(self.pull)
        self.store.set_field(
            self._fresh(),
            ItemField.STATUS,
            derive_status(StatusFacts(stopped=True)),
            marks=marks,
        )

    def _push_passed(self) -> str:
        """Push the commits of the steps that passed. A Planned item with a commit publishes its
        branch and opens its draft; with none, nothing is pushed. The text to add to the comment
        when the push fails, else empty."""
        texts = MESSAGES.roadmap
        try:
            if self.pull is not None:
                self._push_with_lease()
            elif self._has_new_commits():
                self._publish()
        except GitOperationError as exc:
            return texts.implement_stop_push_failed.format(output=mask_secrets(str(exc)))
        except _StopError as exc:
            return texts.implement_stop_push_failed.format(output=mask_secrets(exc.reason))
        return ""


def _error_stop(step: str, exc: Exception, *, push: bool = True) -> _StopError:
    """The stop that an error ends the run with: its class and its message, secrets masked."""
    reason = MESSAGES.roadmap.implement_stop_error.format(
        error=type(exc).__name__, message=mask_secrets(str(exc))
    )
    return _StopError(step, reason, push=push)


def _implement_item(
    store: RoadmapStore,
    repo: str,
    source: Path,
    target: ImplementTarget,
    *,
    model: Any,
    window: int,
) -> _Ended:
    """Run one item: how its run ended (`_Ended`)."""
    default = default_branch(source, operation=GIT_OPERATION)
    with _worktree(source, target) as path:
        run = _ItemRun(store, repo, path, target, model, window, default)
        try:
            run.execute()
        except _ClaimedError as claimed:
            run.yield_to(claimed)
            return _Ended.YIELDED
        except _StopError as stop:
            return run.end_stopped(stop)
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError, subprocess.TimeoutExpired) as exc:
            return run.end_stopped(_error_stop(run.step, exc))
    return _Ended.READY


def apply_implement(
    store: RoadmapStore,
    plan: ImplementPlan,
    *,
    source: Path | str,
    model: Any,
    window: int,
) -> ImplementApplied:
    """Run each selected item of the plan, one after the other. A stopped item does not stop the
    run, and an item whose writes fail is reported while the others still run. Rejected GitHub or
    model credentials stop the run. Raises `RoadmapImplementError` before anything runs unless
    the process is a runner Job for the plan's repository (`require_runner`). It then makes its
    own process unreadable by the shell of an agent, which runs as the same user
    (`deny_environment_reads`), and adopts the orphans of a step (`adopt_orphans`)."""
    require_runner(plan.repo)
    deny_environment_reads()
    adopt_orphans()
    checkout = Path(source)
    ended: dict[_Ended, list[int]] = {kind: [] for kind in _Ended}
    failed: list[ImplementFailure] = []
    for target in plan.selected:
        item = target.item
        try:
            how = _implement_item(store, plan.repo, checkout, target, model=model, window=window)
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError) as exc:
            failed.append(
                ImplementFailure(
                    item.number, item.title, type(exc).__name__, mask_secrets(str(exc))
                )
            )
            continue
        ended[how].append(item.number)
    return ImplementApplied(
        tuple(ended[_Ended.READY]),
        tuple(ended[_Ended.STOPPED]),
        tuple(failed),
        tuple(ended[_Ended.YIELDED]),
    )


def raise_for_failed(failures: Sequence[ImplementFailure]) -> None:
    """Fail the run after the other items ran, naming each item that failed with the class of its
    error. Raises `RoadmapImplementError`."""
    if not failures:
        return
    texts = MESSAGES.roadmap
    items = ", ".join(
        texts.implement_job_failed_item.format(
            number=f.number, error=f.error, reason=f": {f.reason}" if f.reason else ""
        )
        for f in failures
    )
    raise RoadmapImplementError(texts.implement_job_failed.format(count=len(failures), items=items))


__all__ = [
    "ImplementApplied",
    "ImplementFailure",
    "apply_implement",
    "raise_for_failed",
    "require_runner",
]
