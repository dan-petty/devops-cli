"""The writes of the implement job (#2665): the run of one Staged item from its first task group
to a ready pull request, and the stop of an item that cannot get there.

**Where it runs.** The job runs a step only when `roadmap.implement.in_runner` is true. The
step's shell checks the first word of a command and is no security boundary, so the pod of a
runner Job is the sandbox, and the job clears the dumpable flag of its own process so that the
shell, a child of the same user, cannot read the job's environment (#2667). Every `git` command, every GitHub call and every `gh` call of the job
runs in this process, never in the agent's shell; the process runner gives a `git` or `gh` child
the session's token, and any other child (`uv`, `ruff`) none.

**One item.** The job takes over the staged branch in a worktree, sets Status In Progress and
rebases onto the fetched default branch. It runs one step for each group that has an unticked
task, regenerates the documentation, archives the change, rebases again and pushes with a lease.
Then it sets the body of the pull request, comments the outcome of each step, and watches the
checks. A failed check gets one fix step. When the checks pass the job marks the pull request
ready and sets Status In Review. It never merges.

**A stop.** A step that stops, a conflict, a failed command or a check that fails twice stops the
item: the job pushes the commits that passed, comments the step, the reason and the last message
of the agent, sets Status Ready, and records `implement.stopped`. It does not run the item again
until a person comments `implement: retry`.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.config.commands import BIN_DEVOPS, BIN_GIT, BIN_UV
from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS,
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_READY,
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
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.implement import GIT_OPERATION, ImplementPlan, ImplementTarget
from devops_cli.roadmap.implement_pull import WatchKind, failed_log, mark_ready, watch_pull
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    find_change,
    parse_task_groups,
    run_fix_step,
    run_step,
    section_text,
)
from devops_cli.roadmap.stage_change import closing_keyword_in, safe_text
from devops_cli.roadmap.store import ImplementRecordKey, Item, ItemField, RoadmapStore
from devops_cli.security.sanitizer import mask_secrets

_TIMEOUT = CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS
_WHY_HEADINGS = frozenset({"why"})


class _StopError(Exception):
    """An item stops: the job's own signal, caught where the item's run ends. `push` says whether
    the commits that passed are worth pushing."""

    def __init__(
        self, step: str, reason: str, last_message: str = "", *, push: bool = True
    ) -> None:
        super().__init__(reason)
        self.step = step
        self.reason = reason
        self.last_message = last_message
        self.push = push


@dataclass(frozen=True)
class ImplementFailure:
    """An item whose run failed in a way that left it alone: the class of the error and why."""

    number: int
    title: str
    error: str
    reason: str = ""


@dataclass(frozen=True)
class ImplementApplied:
    """What a run did: the items it took to a ready pull request, the items it stopped, and the
    items whose stop or finish could not be written."""

    ready: tuple[int, ...] = ()
    stopped: tuple[int, ...] = ()
    failed: tuple[ImplementFailure, ...] = ()


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
    """The worktree on the staged branch, taken over from `origin`. The worktree and the local
    branch go when the block ends, so the clone keeps its HEAD and holds no issue."""
    report = add_worktree(source, issue=target.item.number, type_=None, slug=None)
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
            raise RoadmapImplementError(MESSAGES.roadmap.implement_left_not_item)
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
        """Run a command of the project in the worktree, outside any agent shell. Raises `_StopError` for the
        current step when it fails or runs out of time."""
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
        self._push()
        self._pull_request()
        self._checks()
        self._ready()

    def _start(self) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["rebase"]
        marks: dict[Any, str | None] = {ImplementRecordKey.PR: str(self.target.pull)}
        if self.target.retry:
            marks[ImplementRecordKey.STOPPED] = None
        self.store.set_field(
            self._fresh(), ItemField.STATUS, CONST_ROADMAP_STATUS_IN_PROGRESS, marks=marks
        )
        self._sync(push_on_conflict=False)

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
            outcome = run_step(
                self.store,
                item=self.number,
                group=group.number,
                source=self.path,
                model=self.model,
                window=self.window,
            )
            self.outcomes.append(outcome)
            if outcome.status is StepStatus.STOPPED:
                raise _StopError(self.step, outcome.reason, outcome.last_message)
            self._record(group=str(group.number), sha=outcome.commit)

    def _finish_change(self) -> None:
        names = MESSAGES.roadmap.implement_step_names
        self.step = names["docs"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "docs", "generate", "--sync-readme"])
        self._commit_if_changed(f"docs: regenerate the documentation (#{self.number})")
        change = self._active_change()
        if change is None:
            return
        self.step = names["archive"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "openspec", "archive", change.name])
        self._commit_if_changed(f"docs(openspec): archive the change (#{self.number})")

    def _push(self) -> None:
        """Rebase onto the default branch again, then push with a lease on the remote tip that the
        job has seen, so a push of anyone else is never overwritten."""
        self.step = MESSAGES.roadmap.implement_step_names["push"]
        self._sync()
        self._push_with_lease()

    def _push_with_lease(self) -> None:
        remote = self._git("rev-parse", f"origin/{self.branch}")
        if remote != self._head():
            self._git("push", f"--force-with-lease={self.branch}:{remote}", "origin", self.branch)

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

    def _pull_request(self) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["pull_request"]
        texts = MESSAGES.roadmap
        archived = self._archived_name()
        body = texts.implement_pull_body.format(
            number=self.number, why=self._why(archived), archived=archived
        )
        client = get_github_session().client
        client.update_pull_body(self.repo, self.target.pull, body)
        lines = "\n".join(self._outcome_line(o) for o in self.outcomes)
        comment = texts.implement_pull_comment.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, lines=lines or "-"
        )
        client.comment_on_pull(self.repo, self.target.pull, comment)

    def _outcome_line(self, outcome: StepOutcome) -> str:
        texts = MESSAGES.roadmap
        commit = texts.implement_pull_comment_commit.format(commit=outcome.commit[:12])
        return texts.implement_pull_comment_line.format(
            step=_step_label(outcome.group) if outcome.group else texts.implement_step_fix,
            title=outcome.title,
            status=outcome.status.value,
            requests=outcome.requests,
            commit=commit if outcome.commit else "",
        )

    def _checks(self) -> None:
        """Watch the checks. A failed check gets one fix step; a second failure stops the item."""
        self.step = MESSAGES.roadmap.implement_step_names["checks"]
        watch = watch_pull(self.repo, self.target.pull, self._head())
        if watch.kind is WatchKind.FAILED and watch.check is not None:
            self._fix(watch.check.name, failed_log(self.repo, watch.check))
            self._push()
            self.step = MESSAGES.roadmap.implement_step_names["checks"]
            watch = watch_pull(self.repo, self.target.pull, self._head())
        if watch.kind is not WatchKind.READY:
            raise _StopError(self.step, watch.reason)

    def _fix(self, check: str, log: str) -> None:
        self.step = MESSAGES.roadmap.implement_step_fix
        outcome = run_fix_step(
            self.store,
            item=self.number,
            fix=FixRequest(check=check, log=log),
            source=self.path,
            model=self.model,
            window=self.window,
        )
        self.outcomes.append(outcome)
        if outcome.status is StepStatus.STOPPED:
            raise _StopError(self.step, outcome.reason, outcome.last_message)

    def _ready(self) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["ready"]
        mark_ready(self.repo, self.target.pull)
        head = self._head()
        marks: dict[Any, str | None] = {
            ImplementRecordKey.SHA: head,
            ImplementRecordKey.PR: str(self.target.pull),
            ImplementRecordKey.SPEND: self._spend(),
        }
        self.store.set_field(
            self._fresh(), ItemField.STATUS, CONST_ROADMAP_STATUS_IN_REVIEW, marks=marks
        )
        spend = json.loads(self._spend())
        self.store.comment(
            self.number,
            MESSAGES.roadmap.implement_comment_finished.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, pull=self.target.pull, **spend
            ),
        )

    # ── The stop ──

    def stop(self, stop: _StopError) -> None:
        """Push what passed, tell the item why, put it back to Ready, and record the step."""
        texts = MESSAGES.roadmap
        note = self._push_passed() if stop.push else ""
        last = safe_text(mask_secrets(stop.last_message))[
            :CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS
        ]
        reason = textwrap.indent(mask_secrets(stop.reason).strip(), "    ")
        self.store.comment(
            self.number,
            texts.implement_comment_stopped.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
                step=stop.step,
                reason=reason,
                last=last or texts.implement_comment_last_none,
                note=note,
            ),
        )
        marks: dict[Any, str | None] = {
            ImplementRecordKey.STOPPED: stop.step,
            ImplementRecordKey.PR: str(self.target.pull),
            ImplementRecordKey.SPEND: self._spend(),
        }
        self.store.set_field(
            self._fresh(), ItemField.STATUS, CONST_ROADMAP_STATUS_READY, marks=marks
        )

    def _push_passed(self) -> str:
        """Push the commits of the steps that passed. The text to add to the comment when the push
        fails, else empty."""
        try:
            self._push_with_lease()
        except GitOperationError as exc:
            return MESSAGES.roadmap.implement_stop_push_failed.format(output=mask_secrets(str(exc)))
        return ""


def _implement_item(
    store: RoadmapStore,
    repo: str,
    source: Path,
    target: ImplementTarget,
    *,
    model: Any,
    window: int,
) -> bool:
    """Run one item. True when its pull request is ready, False when the item is stopped."""
    default = default_branch(source, operation=GIT_OPERATION)
    with _worktree(source, target) as path:
        run = _ItemRun(store, repo, path, target, model, window, default)
        try:
            run.execute()
        except _StopError as stop:
            run.stop(stop)
            return False
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError, subprocess.TimeoutExpired) as exc:
            texts = MESSAGES.roadmap
            reason = texts.implement_stop_error.format(
                error=type(exc).__name__, message=mask_secrets(str(exc))
            )
            run.stop(_StopError(run.step, reason))
            return False
    return True


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
    the process is a runner Job for the plan's repository (`require_runner`). It then makes its own process unreadable by the shell
    of an agent, which runs as the same user (`deny_environment_reads`)."""
    require_runner(plan.repo)
    deny_environment_reads()
    adopt_orphans()
    checkout = Path(source)
    ready: list[int] = []
    stopped: list[int] = []
    failed: list[ImplementFailure] = []
    for target in plan.selected:
        item = target.item
        try:
            done = _implement_item(store, plan.repo, checkout, target, model=model, window=window)
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError) as exc:
            failed.append(
                ImplementFailure(
                    item.number, item.title, type(exc).__name__, mask_secrets(str(exc))
                )
            )
            continue
        (ready if done else stopped).append(item.number)
    return ImplementApplied(tuple(ready), tuple(stopped), tuple(failed))


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
