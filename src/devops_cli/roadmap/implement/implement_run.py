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
Each other push (the first push of a Planned item, a `wip:` push, a checkpoint and the push of a
stop) also sends a commit that holds the default branch (`_current_tip`, #4380).
Then it sets the title and the body of the pull request, comments the outcome of each step, and
watches the checks. A failed check gets one fix step. When the checks pass the job marks the pull
request ready and sets Status In Review. It never merges.

**A Planned item** (#2714) has its plan on the default branch and no branch. The job makes the
branch `<type>/<issue>-<slug>` at the fetched default branch, and goes on as above. A pull request
needs a commit past its base, so the job publishes the branch at its first push (`_publish`): it
pushes with `-u`, opens the draft, and records `implement.branch` and `implement.pr`. A stop before
the first commit pushes nothing. A stop after it publishes what passed, so a retry finds the branch
and the draft and takes them over as a Staged item.

**Work in progress** (#3054). A step commits each ticked task whose verification passes as a `wip:`
commit. The job pushes it at once (`_keep`) when a task is left, and records `implement.wip`, so a
pod that dies loses only the work after the last tick. A stop discards only that work. The next run
takes the branch with its `wip:` commits, shows the kept ticks to the agent, and its step folds them
into its own commit.

**A stop.** A step that stops, a conflict, a failed command or a check that fails twice stops the
item: the job pushes the commits that passed (also a stop in the scoped checks, #3645: the finished
groups stay on the branch, and the draft is not marked ready), comments the step, the reason and the
last message of the agent, sets Status Blocked, and records `implement.stopped`. The comment starts
with the class of the failure, the action taken and the action left (`failure.py`, #3065), and the
class is recorded in `implement.failure`. It does not run the item again until a clear rule of the
Service removes the stop: a person's comment `implement: retry`, a new runner image
(`stop_clear.py`), or, for a Job that ended with no result, a continuation (#3721).

**A claim** (#2910). The Service holds the item with `owner/service` while the Job runs. The job
reads the item before each unticked task group, when a step stops, and before the push. When an
agent or a person holds it by then, the job ends the item at once: it pushes nothing, opens no
pull request, comments why, and changes neither the Status nor the owner. The groups that passed stay in the
worktree, which the job removes; the new owner starts from the branch on `origin`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import textwrap
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, NoReturn

from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as ModelValidationError

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.config.commands import BIN_DEVOPS, BIN_GIT, BIN_UV
from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
    CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_REASON_PATHS,
    CONST_ROADMAP_IMPLEMENT_STEPS_FILE,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import acts_as_github_app, run_subprocess
from devops_cli.core.process_hardening import adopt_orphans, deny_environment_reads
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubOperationError,
    GitHubUnauthenticatedError,
    GitOperationError,
    RoadmapImplementError,
    ValidationError,
)
from devops_cli.exceptions.roadmap import OverWindowError
from devops_cli.git.worktree_add import add_worktree
from devops_cli.github.check_verdict import PRCheckItem, read_check_runs
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.failure import (
    FailureAction,
    FailureClass,
    FailureEvidence,
    StepName,
    classify_failure,
    failure_lines,
    left_action,
)
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.implement.implement import GIT_OPERATION, ImplementPlan, ImplementTarget
from devops_cli.roadmap.implement.implement_amend import (
    Amendment,
    Applied,
    PlanRequest,
    _record_amendment,
    judge,
    parse_request,
)
from devops_cli.roadmap.implement.implement_base_replay import BaseStatus
from devops_cli.roadmap.implement.implement_hooks import install_hook_environments, trusted_config
from devops_cli.roadmap.implement.implement_limits import ItemSpend
from devops_cli.roadmap.implement.implement_pull import (
    Answer,
    ChangeFacts,
    Draft,
    DraftKind,
    Watch,
    WatchKind,
    draft_readiness,
    failed_log,
    mark_ready,
    watch_pull,
)
from devops_cli.roadmap.implement.implement_scoped_ci import (
    ScopedResult,
    plan_tests,
    run_scoped_checks,
    scoped_checks,
)
from devops_cli.roadmap.implement.implement_shell_policy import shown
from devops_cli.roadmap.implement.implement_step import (
    EarlierStop,
    FixRequest,
    StepOutcome,
    StepStatus,
    TierSpend,
    find_change,
    run_fix_step,
    run_step,
)
from devops_cli.roadmap.implement.implement_steps import ProjectStep, declared_steps
from devops_cli.roadmap.implement.implement_trace import (
    ImplementTrace,
    SummaryRow,
    last_failing_command,
    summary_table,
)
from devops_cli.roadmap.implement.implement_wip import WipCommit, kept_commits, wip_base
from devops_cli.roadmap.plan_read import PlanReadError, merged_recorded_tests
from devops_cli.roadmap.premise import false_premises
from devops_cli.roadmap.pull_form import BODY_MAX_CHARS, build_body, title_problems
from devops_cli.roadmap.pull_labels import (
    add_pull_labels,
    declared_labels,
    remove_pull_labels,
    stale_labels,
)
from devops_cli.roadmap.return_item import apply_return, plan_return
from devops_cli.roadmap.stage.stage_change import (
    closing_keyword_in,
    criteria_section,
    delivery_title,
    group_text,
    measure_groups,
    safe_text,
)
from devops_cli.roadmap.stage.stage_criteria import StageCriterion, criterion_problems
from devops_cli.roadmap.stage.stage_form import form_problems
from devops_cli.roadmap.stage.stage_paths import StagedTree, path_problems
from devops_cli.roadmap.stage.stage_split import ask_split
from devops_cli.roadmap.status_sync import StatusFacts, derive_status
from devops_cli.roadmap.step_files import TaskGroup, parse_task_groups, section_text
from devops_cli.roadmap.step_metrics import observe_implement
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ImplementResult,
    Item,
    ItemField,
    RoadmapStore,
)
from devops_cli.roadmap.title_labels import title_labels
from devops_cli.security.sanitizer import mask_secrets

_WHY_HEADINGS = frozenset({"why"})


# The run id of the comment on the pull request for a run that no Service started (#4070).
_MANUAL_RUN = "manual"


class _RecordedSpend(BaseModel):
    """The spend that the record `implement.spend` holds, as `JobRun._spend` writes it. A key that
    an older record lacks takes its empty value (#4070)."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    steps: list[dict[str, Any]] = []
    tiers: dict[str, TierSpend] = {}


class _StopError(Exception):
    """An item stops: the job's own signal, caught where the item's run ends. `push` says whether
    the commits that passed are worth pushing. `kept_branch` says that the stop ends the scoped checks
    of a finished item, so the comment names the branch as the kept work (#3645). `diff` is the diff
    of the work that a stopped step discarded, and `diff_cut` says that it was cut (#2721). `status`
    is the exit status of the command that failed, `check` the name of the check that failed,
    `check_log` the log of that check, `repair_rounds` the fix rounds that the job ran before it
    stopped, and `tier_changes` the tier moves of the step: they are the evidence of the failure
    class (#3065, #3060, #3476).
    `failure_class` is the class that the site of the stop passes, when it knows its cause.
    `conflict_files` are the masked files that a rebase conflict left unmerged (#3646)."""

    def __init__(
        self,
        step: str,
        reason: str,
        last_message: str = "",
        *,
        push: bool = True,
        kept_branch: bool = False,
        diff: str = "",
        diff_cut: bool = False,
        status: int | None = None,
        check: str = "",
        check_log: str = "",
        repair_rounds: int = 0,
        tier_changes: int = 0,
        failure_class: FailureClass | None = None,
        action_left: FailureAction | None = None,
        conflict_files: Sequence[str] = (),
    ) -> None:
        super().__init__(reason)
        self.step = step
        self.reason = reason
        self.last_message = last_message
        self.push = push
        self.kept_branch = kept_branch
        self.diff = diff
        self.diff_cut = diff_cut
        self.status = status
        self.check = check
        self.check_log = check_log
        self.repair_rounds = repair_rounds
        self.tier_changes = tier_changes
        self.failure_class = failure_class
        self.action_left = action_left
        self.conflict_files = tuple(conflict_files)


class _ClaimedError(Exception):
    """An agent or a person claimed the item: the job's own signal that the run ends at the next
    group boundary, caught where the item's run ends. `owner` is the claim in lower case and
    `boundary` says where the run ended."""

    def __init__(self, owner: str, boundary: str) -> None:
        super().__init__(owner)
        self.owner = owner
        self.boundary = boundary


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
    returned: tuple[int, ...] = ()


def _stopped_by(step: str, outcome: StepOutcome, *, check: str = "", log: str = "") -> _StopError:
    """The stop of an item for a step that stopped, with the class that the step passes, the diff
    of its discarded work and the tier moves that the step made before it stopped. A fix step
    gives the check that it was to fix and the log of that check (#3476)."""
    return _StopError(
        step,
        outcome.reason,
        outcome.last_message,
        diff=outcome.diff,
        diff_cut=outcome.diff_cut,
        check=check,
        check_log=log,
        repair_rounds=outcome.repair_rounds,
        tier_changes=max(0, len(outcome.tiers) - 1),
        failure_class=outcome.failure_class,
    )


def _conflict_files(output: str) -> list[str]:
    """The paths that `git diff --name-only -z` lists, masked and escaped so that a secret or a
    control character in a path does not leave the job (#3646)."""
    return [shown(mask_secrets(path)) for path in output.split("\0") if path]


def _files_lines(files: Sequence[str]) -> str:
    """The paths of `files` as a list of lines, cut to `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
    paths, with the count of the paths that the cut leaves out."""
    lines = [f"- {path}" for path in files[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS]]
    if len(files) > CONST_ROADMAP_IMPLEMENT_REASON_PATHS:
        count = len(files) - CONST_ROADMAP_IMPLEMENT_REASON_PATHS
        lines.append(MESSAGES.roadmap.implement_paths_more.format(count=count).strip())
    return "\n".join(lines)


def _check_section(check: str, log: str) -> str:
    """The first part of the stop comment: the failed check, and the end of its log when the stop
    has one. Empty when no check is known (#3476)."""
    texts = MESSAGES.roadmap
    if not check:
        return ""
    name = check.replace("`", "'")
    if not log:
        return texts.implement_comment_check.format(name=name)
    return texts.implement_comment_check_log.format(name=name, fence=code_fence(log), log=log)


def _check_log_end(log: str) -> str:
    """The end of the log of a failed check for a comment and the record: secrets masked, each
    line escaped so it holds no raw control character, and at most
    `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters (#3476). The masking reads the last
    `4 * CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters: a secret that the start of that part
    splits lies in the part that the cut drops."""
    window = log[-4 * CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS :]
    lines = mask_secrets(window).strip().splitlines()
    text = "\n".join(shown(line, CONST_ROADMAP_IMPLEMENT_REASON_CHARS) for line in lines)
    return text[-CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS:]


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


def _outcome_label(outcome: StepOutcome) -> str:
    """The label of the step that left `outcome`: its group, or the fix of a failed check."""
    return _step_label(outcome.group) if outcome.group else MESSAGES.roadmap.implement_step_fix


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


def _parse_tasks_criteria(tasks_md: str) -> list[StageCriterion]:
    if "## Criteria" not in tasks_md:
        return []
    section = tasks_md.partition("## Criteria\n\n")[2].partition("\n\n## ")[0]
    criteria: list[StageCriterion] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        content = line[2:].strip()
        if content.startswith("Group "):
            num_part, _, text = content[6:].partition(":")
            if num_part.isdigit():
                criteria.append(StageCriterion(group=int(num_part), criterion=text.strip()))
        elif content.startswith("Pending person:"):
            rest = content[15:].strip()
            crit, _, reason = rest.partition(",")
            criteria.append(
                StageCriterion(
                    group="pending-person",
                    criterion=crit.strip(),
                    reason=reason.strip(),
                )
            )
    return criteria


def _replace_criteria_section(tasks_md: str, new_criteria_sec: str) -> str:
    if "## Criteria" in tasks_md:
        start_idx = tasks_md.index("## Criteria")
        end_idx = tasks_md.find("\n## ", start_idx + len("## Criteria"))
        if end_idx != -1:
            return tasks_md[:start_idx] + new_criteria_sec + tasks_md[end_idx + 1 :]
        return tasks_md[:start_idx] + new_criteria_sec
    if "## Workflow follow-up" in tasks_md:
        wf_idx = tasks_md.index("## Workflow follow-up")
        return tasks_md[:wf_idx] + new_criteria_sec + tasks_md[wf_idx:]
    if "## Amendments" in tasks_md:
        am_idx = tasks_md.index("## Amendments")
        return tasks_md[:am_idx] + new_criteria_sec + tasks_md[am_idx:]
    return tasks_md.rstrip() + "\n\n" + new_criteria_sec


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
    model_for_tier: Callable[[str], Any] | None = None
    splitter: Any = None
    split_done: bool = False
    change: str = ""
    outcomes: list[StepOutcome] = field(default_factory=list)
    amendments: list[Amendment] = field(default_factory=list)
    # Every run of a scoped check (#3043), in order, the failed runs too, and the notes that say why
    # the tests check was narrower than the changed files.
    scoped: list[ScopedResult] = field(default_factory=list)
    scoped_notes: list[str] = field(default_factory=list)
    # The project steps that the job skipped, because the default branch does not declare them
    # (#3484), in order, each once.
    skipped_steps: list[ProjectStep] = field(default_factory=list)
    # The trace of the run (#3032): the events of the steps and of the commands of the job.
    trace: ImplementTrace = field(default_factory=ImplementTrace)
    _step: str = field(default="", init=False, repr=False)
    # The draft pull request: the target's, or for a Planned item the one `_publish` opens.
    pull: int | None = field(init=False)
    # The spend of the earlier Jobs of the item, from `implement.spend` (#4070).
    earlier: _RecordedSpend = field(default_factory=_RecordedSpend, init=False)
    # The heads that earlier Jobs and this Job checked and pushed (#4070), from the record.
    checked_sha: str | None = field(default=None, init=False)
    published_sha: str | None = field(default=None, init=False)
    # The comment of this run on the pull request: its id once it is posted or found, and whether
    # the comments were listed already (#4070).
    comment_id: int | None = field(default=None, init=False)
    comments_listed: bool = field(default=False, init=False)
    # The stop of the earlier Job, which the first step of the run gets once (#4071).
    handoff: EarlierStop | None = field(default=None, init=False)
    returned: bool = False
    checkpoints_off: bool = False
    passed: bool = False
    # The last `wip:` commit of the group that runs (#3054), or None.
    wip: WipCommit | None = None
    # The time at which the run of the item began, for the time limit of the item (#3053).
    started: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.pull = self.target.pull
        held = self.target.item.job_record
        if not self.target.retry and (recorded := held.get(ImplementRecordKey.SPEND)):
            self.earlier = _RecordedSpend.model_validate_json(recorded)
        self.checked_sha = held.get(ImplementRecordKey.CHECKED_SHA)
        self.published_sha = held.get(ImplementRecordKey.PUBLISHED_SHA)

    # ── Small helpers ──

    @property
    def step(self) -> str:
        """The step that runs now. It labels the events of the trace."""
        return self._step

    @step.setter
    def step(self, value: str) -> None:
        self._step = value
        self.trace.step = value

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

    def _item_spend(self) -> ItemSpend:
        """What the steps of this run spent so far, for the budgets of the next step (#3053)."""
        return ItemSpend(
            input_tokens=self.earlier.input_tokens
            + sum(outcome.input_tokens for outcome in self.outcomes),
            started=self.started,
        )

    def _spend(self) -> str:
        """The spend of every step of the item, itemized under the tier that served it (#3060), and
        the input tokens of the first request of each step (#3499). The trace drops its oldest
        events when it is long, so the size of a first request is kept here. It is the sum of the
        earlier Jobs of the item and this Job (#4070)."""
        tiers: dict[str, dict[str, int]] = {
            tier: spend.model_dump() for tier, spend in self.earlier.tiers.items()
        }
        for outcome in self.outcomes:
            for tier, spend in outcome.tier_spend.items():
                held = tiers.setdefault(
                    tier, {"requests": 0, "input_tokens": 0, "output_tokens": 0}
                )
                held["requests"] += spend.requests
                held["input_tokens"] += spend.input_tokens
                held["output_tokens"] += spend.output_tokens
        return json.dumps(
            {
                "requests": self.earlier.requests + sum(o.requests for o in self.outcomes),
                "input_tokens": self.earlier.input_tokens
                + sum(o.input_tokens for o in self.outcomes),
                "output_tokens": self.earlier.output_tokens
                + sum(o.output_tokens for o in self.outcomes),
                "steps": [
                    *self.earlier.steps,
                    *(
                        {"step": _outcome_label(o), "first_request_tokens": o.first_request_tokens}
                        for o in self.outcomes
                    ),
                ],
                "tiers": tiers,
            }
        )

    def _record(self, **marks: str | int | None) -> None:
        keys = {
            "group": ImplementRecordKey.GROUP,
            "sha": ImplementRecordKey.SHA,
            "spend": ImplementRecordKey.SPEND,
            "repair_rounds": ImplementRecordKey.REPAIR_ROUNDS,
        }
        written: dict[Any, str | int | None] = {keys[name]: value for name, value in marks.items()}
        if "group" in marks:
            written[ImplementRecordKey.WIP] = None
            self.wip = None
        written[ImplementRecordKey.TRACE] = self.trace.encode()
        self.store.set_marks(self._fresh(), written)

    def _program(self, argv: Sequence[str]) -> None:
        """Run a command of the project in the worktree, outside any agent shell. Raises
        `_StopError` for the current step when it fails or runs out of time."""
        shown = " ".join(argv)
        texts = MESSAGES.roadmap
        limit = load_settings().roadmap.implement.command_timeout_seconds
        try:
            done = run_subprocess(list(argv), cwd=self.path, quiet=True, timeout=limit)
        except subprocess.TimeoutExpired as exc:
            self.trace.check(shown, None)
            reason = texts.implement_stop_program_timeout.format(command=shown, seconds=limit)
            raise _StopError(self.step, reason) from exc
        self.trace.check(shown, done.returncode)
        if done.returncode != 0:
            output = _tail(f"{done.stdout or ''}{done.stderr or ''}")
            reason = texts.implement_stop_program_failed.format(
                command=shown, status=done.returncode, output=output
            )
            raise _StopError(self.step, reason, status=done.returncode)

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
        if self.returned:
            return
        self._finish_change()
        self._require_unclaimed(MESSAGES.roadmap.implement_boundary_end)
        pull = self._push()
        self._pull_request(pull)
        self._checks(pull)
        self._ready(pull)

    def _start(self) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["rebase"]
        marks: dict[Any, str | None] = {
            ImplementRecordKey.BRANCH: self.branch,
            ImplementRecordKey.TRACE: None,
        }
        if self.pull is not None:
            marks[ImplementRecordKey.PR] = str(self.pull)
        if not self.target.item.job_record.get(ImplementRecordKey.BASE):
            marks[ImplementRecordKey.BASE] = self._base()
        record = self.target.item.job_record
        self.handoff = _earlier_stop(
            record.get(ImplementRecordKey.CHECK_LOG), record.get(ImplementRecordKey.CONFLICT)
        )
        marks[ImplementRecordKey.RESULT] = None
        marks[ImplementRecordKey.CHECK_LOG] = None
        marks[ImplementRecordKey.CONFLICT] = None
        if self.target.retry:
            marks[ImplementRecordKey.STOPPED] = None
            marks[ImplementRecordKey.FAILURE] = None
            marks[ImplementRecordKey.CHECK] = None
            marks[ImplementRecordKey.SPEND] = None
            marks[ImplementRecordKey.SPEND_COUNTED] = None
        self.store.set_field(
            self._fresh(), ItemField.STATUS, CONST_ROADMAP_STATUS_IN_PROGRESS, marks=marks
        )
        self._sync(push_on_conflict=False)
        self._install_hooks()

    def _base(self) -> str:
        if self.target.pull is None and not self._git(
            "ls-remote", "--heads", "origin", self.branch
        ):
            return "new"
        return self._git("rev-parse", f"origin/{self.branch}")

    def _hooks_config(self) -> Path | None:
        """The configuration of the hooks as the default branch has it, or None when it has none.
        Every hook run reads this copy, never the file of the checkout, which the agent can edit
        (#3043)."""
        return trusted_config(self.path, f"origin/{self.default}")

    def _recorded_tests(self) -> frozenset[str]:
        """The tests that the plan on the default branch records (#3490). A person merged that
        text, so it holds what the owner allows under rule 5 of `AGENTS.md`. The job never reads the
        file of the checkout, which the agent can edit, and a plan that is only on its staged branch
        records none. A section that the reader refuses stops the item: the plan is at fault."""
        try:
            return merged_recorded_tests(
                self.path, f"origin/{self.default}", self.number, operation=GIT_OPERATION
            )
        except PlanReadError as error:
            raise _StopError(
                self.step,
                MESSAGES.roadmap.plan_check_read.format(path=error.path, reason=error.reason),
                failure_class=FailureClass.PLAN_DEFECT,
            ) from error

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
        self._rebase(self.path, push_on_conflict=push_on_conflict)

    def _rebase(self, path: Path, *, push_on_conflict: bool = True) -> None:
        """Rebase the checkout `path` onto `origin/<default>`. The conflict path of `_sync`."""
        try:
            git(path, "rebase", f"origin/{self.default}", operation=GIT_OPERATION)
        except GitOperationError as exc:
            timeout = load_settings().roadmap.implement.command_timeout_seconds
            unmerged = run_subprocess(
                [BIN_GIT, "-C", str(path), "diff", "--name-only", "--diff-filter=U", "-z"],
                check=False,
                quiet=True,
                timeout=timeout,
            )
            files = _conflict_files(unmerged.stdout) if unmerged.returncode == 0 else []
            aborted = run_subprocess(
                [BIN_GIT, "-C", str(path), "rebase", "--abort"],
                check=False,
                quiet=True,
                timeout=timeout,
            )
            texts = MESSAGES.roadmap
            reason = texts.implement_stop_rebase.format(branch=self.default, output=str(exc))
            if files:
                reason += texts.implement_stop_rebase_files.format(files=_files_lines(files))
            if aborted.returncode != 0:
                reason += texts.implement_stop_abort_failed.format(output=_tail(aborted.stderr))
            raise _StopError(
                self.step,
                reason,
                push=push_on_conflict,
                failure_class=FailureClass.CONFLICT,
                conflict_files=files[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS],
            ) from exc

    def _require_unclaimed(self, boundary: str) -> None:
        """Raise `_ClaimedError` when an agent or a person holds the item now (#2910). The
        Service's own claim holds nothing against the job."""
        owner = claimed_by(self._fresh())
        if owner is not None:
            raise _ClaimedError(owner, boundary)

    def _return_premise(self, request: PlanRequest) -> None:
        self._return_to_new(MESSAGES.roadmap.implement_comment_premise_failed, request.evidence)

    def _check_premise(self, group: TaskGroup) -> bool:
        """Return the item to New, and say so, when a task of the behavior group `group` adds a guard
        that the branch already defines (#3417). The check reads the last commit that is no `wip:`
        commit, so the guard that an earlier attempt of this group kept is no defect of the plan. It
        runs before the step, so a false premise costs no model request and writes no file. A group
        of another kind adds no product guard, so it gets no check."""
        if not group.is_behavior:
            return False
        evidence = false_premises(self.path, wip_base(self._git), group)
        if not evidence:
            return False
        self._return_to_new(MESSAGES.roadmap.implement_comment_premise_defined, "\n".join(evidence))
        return True

    def _return_to_new(self, template: str, evidence: str) -> None:
        """Return the item to New with a comment of `template`, and clear the record of the run."""
        self._withdraw()
        evidence = mask_secrets(evidence.strip())[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS]
        comment = template.format(marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, evidence=evidence)
        apply_return(self.store, plan_return(self.store, self.number, comment, self.repo))
        self.store.set_marks(
            self._fresh(),
            {
                ImplementRecordKey.GROUP: None,
                ImplementRecordKey.SHA: None,
                ImplementRecordKey.WIP: None,
                ImplementRecordKey.BRANCH: None,
                ImplementRecordKey.PR: None,
                ImplementRecordKey.BASE: None,
                ImplementRecordKey.SPEND: None,
                ImplementRecordKey.SPEND_COUNTED: None,
                ImplementRecordKey.CHECKED_SHA: None,
                ImplementRecordKey.PUBLISHED_SHA: None,
                ImplementRecordKey.RESULT: ImplementResult.RETURNED.value,
            },
        )
        self.returned = True

    def _raise_question(self, outcome: StepOutcome, reason: str) -> NoReturn:
        raise _StopError(
            self.step,
            reason,
            outcome.last_message,
            diff=outcome.diff,
            diff_cut=outcome.diff_cut,
            failure_class=FailureClass.PLAN_DEFECT,
            action_left=FailureAction.WAIT,
        )

    def _handle_request_stop(
        self,
        group_number: int,
        request: PlanRequest,
        outcome: StepOutcome,
        tasks_text: str,
        tasks_file: Path,
        amended_groups: set[int],
    ) -> bool:
        texts = MESSAGES.roadmap
        if request.kind == "premise":
            if request.evidence.strip():
                self._return_premise(request)
                return True
            self._raise_question(outcome, texts.implement_stop_question_empty_premise)
        if group_number in amended_groups:
            self._raise_question(
                outcome,
                texts.implement_stop_question_second.format(
                    group=group_number, defect=request.defect, evidence=request.evidence
                ),
            )
        if request.kind == "scope":
            self._raise_question(
                outcome,
                texts.implement_stop_question_scope.format(
                    defect=request.defect, evidence=request.evidence
                ),
            )
        return self._apply_or_refuse(
            group_number, request, outcome, tasks_text, tasks_file, amended_groups
        )

    def _apply_or_refuse(
        self,
        group_number: int,
        request: PlanRequest,
        outcome: StepOutcome,
        tasks_text: str,
        tasks_file: Path,
        amended_groups: set[int],
    ) -> bool:
        tree = StagedTree.read(self.path, operation=GIT_OPERATION)
        judged = judge(request, tasks_text, tree)
        if isinstance(judged, Applied):
            tasks_file.write_text(judged.tasks_md, encoding="utf-8")
            self._commit_if_changed(
                f"docs(openspec): amend the plan of group {group_number} (#{self.number})"
            )
            self.amendments.append(judged.amendment)
            amended_groups.add(group_number)
            return False
        texts = MESSAGES.roadmap
        self._raise_question(
            outcome,
            texts.implement_stop_question_refused.format(
                rule=judged.reason, defect=request.defect, evidence=request.evidence
            ),
        )

    def _handle_over_window(
        self,
        group: TaskGroup,
        err: OverWindowError,
        change: Path,
        tasks_text: str,
        tasks_file: Path,
        tasks: list[TaskGroup],
    ) -> None:
        texts = MESSAGES.roadmap
        if self.splitter is None:
            raise _StopError(
                self.step,
                texts.implement_stop_split_missing,
                failure_class=FailureClass.PLAN_DEFECT,
                action_left=FailureAction.WAIT,
            )
        if self.split_done:
            raise _StopError(
                self.step,
                texts.implement_stop_split_second,
                failure_class=FailureClass.PLAN_DEFECT,
                action_left=FailureAction.WAIT,
            )

        current_criteria = _parse_tasks_criteria(tasks_text)
        asked = {
            "number": self.number,
            "title": self.target.item.title,
            "budget": err.limit,
            "groups": [
                {
                    "number": group.number,
                    "title": group.title,
                    "tokens": err.measured,
                    "over_budget": True,
                    "text": group.text,
                }
            ],
            "criteria": [c.model_dump() for c in current_criteria],
        }
        split = ask_split(self.splitter, asked)
        self.split_done = True

        form_probs = form_problems(split.groups)
        if form_probs:
            raise _StopError(
                self.step,
                texts.implement_stop_split_invalid.format(problems=" ".join(form_probs)),
                failure_class=FailureClass.PLAN_DEFECT,
                action_left=FailureAction.WAIT,
            )

        tree = StagedTree.read(self.path, operation=GIT_OPERATION)
        path_probs = path_problems(split.groups, tree)
        if path_probs:
            raise _StopError(
                self.step,
                texts.implement_stop_split_invalid.format(problems=" ".join(path_probs)),
                failure_class=FailureClass.PLAN_DEFECT,
                action_left=FailureAction.WAIT,
            )

        new_total_groups = len(tasks) - 1 + len(split.groups)
        crit_probs = criterion_problems(split.criteria, self.target.item.body, new_total_groups)
        if crit_probs:
            raise _StopError(
                self.step,
                texts.implement_stop_split_invalid.format(problems=" ".join(crit_probs)),
                failure_class=FailureClass.PLAN_DEFECT,
                action_left=FailureAction.WAIT,
            )

        change_docs = [
            (change / name).read_text(encoding="utf-8")
            for name in ("proposal.md", "design.md")
            if (change / name).exists()
        ]
        shared = [self.target.item.body, *change_docs]
        measured = measure_groups(self.path, split.groups, shared=shared)
        over = next((m for m in measured if m.tokens > err.limit), None)
        if over is not None:
            raise _StopError(
                self.step,
                texts.implement_stop_split_over_budget.format(
                    title=over.group.title, tokens=over.tokens
                ),
                failure_class=FailureClass.PLAN_DEFECT,
                action_left=FailureAction.WAIT,
            )

        shift = len(split.groups) - 1
        new_md = tasks_text
        for g in reversed(tasks):
            if g.number > group.number:
                new_num = g.number + shift
                renumbered_text = re.sub(
                    rf"^## {g.number}\.", f"## {new_num}.", g.text, count=1, flags=re.MULTILINE
                )
                renumbered_text = re.sub(
                    rf"- \[([ xX])\] {g.number}\.(\d+)", rf"- [\1] {new_num}.\2", renumbered_text
                )
                new_md = new_md.replace(g.text, renumbered_text, 1)

        split_rendered = "\n\n".join(
            group_text(group.number + i, sg).rstrip() for i, sg in enumerate(split.groups)
        )
        new_md = new_md.replace(group.text, split_rendered, 1)

        if split.criteria:
            new_crit = criteria_section(split.criteria)
            new_md = _replace_criteria_section(new_md, new_crit)

        split_amendment = Amendment(
            group=group.number,
            kind="split",
            defect="group over the window limit",
            evidence=f"{err.measured} tokens > {err.limit} tokens",
            old=f"group {group.number}",
            new=f"groups {group.number} to {group.number + len(split.groups) - 1}",
        )
        new_md = _record_amendment(new_md, split_amendment.bullet())
        self.amendments.append(split_amendment)
        tasks_file.write_text(new_md, encoding="utf-8")
        self._commit_if_changed(f"docs(openspec): split group {group.number} (#{self.number})")

    def _groups(self) -> None:
        change = self._active_change()
        if change is None:
            return
        self.change = change.name
        tasks_file = change / "tasks.md"
        amended_groups: set[int] = set()

        while True:
            tasks_text = tasks_file.read_text(encoding="utf-8")
            tasks = parse_task_groups(tasks_text)
            group = next((g for g in tasks if not all(task.ticked for task in g.tasks)), None)
            if group is None:
                break
            self.step = _step_label(group.number)
            self._require_unclaimed(
                MESSAGES.roadmap.implement_boundary_group.format(group=group.number)
            )
            if self._check_premise(group):
                return
            self._checkpoint()
            try:
                outcome = run_step(
                    self.store,
                    item=self.number,
                    group=group.number,
                    source=self.path,
                    model=self.model,
                    window=self.window,
                    hooks=self._hooks_config(),
                    model_for_tier=self.model_for_tier,
                    trace=self.trace,
                    on_wip=self._keep,
                    spend=self._item_spend(),
                    recorded_tests=self._recorded_tests(),
                    earlier=self._take_earlier(),
                )
            except OverWindowError as err:
                self._handle_over_window(group, err, change, tasks_text, tasks_file, tasks)
                continue
            self.outcomes.append(outcome)
            if outcome.status is StepStatus.STOPPED:
                # The step kept its `wip:` commits (#3054), so the file differs from the text above.
                tasks_text = tasks_file.read_text(encoding="utf-8")
                request = parse_request(outcome.last_message)
                if request is not None:
                    returned = self._handle_request_stop(
                        group.number, request, outcome, tasks_text, tasks_file, amended_groups
                    )
                    if returned:
                        return
                    continue
                raise _stopped_by(self.step, outcome)
            self._record(
                group=str(group.number),
                sha=outcome.commit,
                spend=self._spend(),
                repair_rounds=sum(o.repair_rounds for o in self.outcomes),
            )
            self.passed = True

    def _take_earlier(self) -> EarlierStop | None:
        """The stop of the earlier Job for the step that runs now, and none for the steps after
        it: the first step either fixes the cause or stops (#4071)."""
        earlier, self.handoff = self.handoff, None
        return earlier

    def _checkpoint(self) -> None:
        """Push the groups that passed in this run, so that a killed runner loses none (#3677).
        A failed push goes to the log, and the run makes no more checkpoint pushes."""
        if self.checkpoints_off or not self.passed:
            return
        if failed := self._push_passed():
            self.checkpoints_off = True
            print_muted(failed.strip(), to_stderr=True, safe=True)

    def _withdraw(self) -> None:
        """Take the groups that the checkpoints pushed off the item branch, before a return to New
        (#3677). A Staged item gets the tip of `implement.base` back; a Planned item loses its
        branch and its draft. Both pushes carry a lease on the tip that the job saw, so a push of a
        person stays. A push that fails stops the item as Blocked and returns nothing."""
        base = self._fresh().job_record.get(ImplementRecordKey.BASE)
        if not base:
            return
        try:
            if base == "new" and not self._git("ls-remote", "--heads", "origin", self.branch):
                return
            tip = self._git("rev-parse", f"origin/{self.branch}")
            lease = f"--force-with-lease={self.branch}:{tip}"
            if base == "new":
                self._git("push", lease, "origin", "--delete", self.branch)
                if self.pull is not None:
                    get_github_session().client.close_pull(self.repo, self.pull)
            elif tip != base:
                self._git("push", lease, "origin", f"{base}:refs/heads/{self.branch}")
        except (GitOperationError, DevOpsCLIError) as exc:
            reason = MESSAGES.roadmap.implement_stop_withdraw_failed.format(
                branch=self.branch, output=mask_secrets(str(exc))
            )
            raise _StopError(self.step, reason, push=False) from exc

    def _keep(self, commit: WipCommit) -> None:
        """Take note of a `wip:` commit of the step (#3054). When tasks are left, push it and
        record it at once, so that a pod that dies keeps the work: the next Job takes the branch
        from `origin`. A commit that ticks the last task waits for the push of the end or of the
        stop, because the exit checks of the step follow at once. A push that fails does not stop
        the step. The line goes to the log, and the next push tries again."""
        self.wip = commit
        if commit.done >= commit.total:
            return
        if failed := self._push_passed(in_step=True):
            print_muted(failed.strip(), to_stderr=True, safe=True)
        self.store.set_marks(self._fresh(), {ImplementRecordKey.WIP: _wip_record(commit)})

    def _kept_note(self, *, branch: bool = False) -> str:
        """The part of the stop comment that says what the job kept and where: the branch, the
        count of `wip:` commits on it and the last one (#3054). With no `wip:` commit, `branch`
        says that the groups finished, so the note names the branch and its last commit (#3645).
        Empty when the job kept nothing to name."""
        kept = kept_commits(self._git, f"origin/{self.default}")
        if not kept:
            if not (branch and self._has_new_commits()):
                return ""
            return MESSAGES.roadmap.implement_stop_kept_branch.format(
                branch=self.branch, sha=self._head()
            )
        return MESSAGES.roadmap.implement_stop_kept.format(
            count=len(kept),
            commits="commit" if len(kept) == 1 else "commits",
            branch=self.branch,
            sha=kept[0],
        )

    def _runs(self, step: ProjectStep) -> bool:
        """Whether the job runs `step`: the default branch declares it. A step that it does not
        declare is noted for the comment, once (#3484)."""
        if step in declared_steps(self.path, f"origin/{self.default}"):
            return True
        if step not in self.skipped_steps:
            self.skipped_steps.append(step)
        return False

    def _generate_docs(self) -> None:
        """Generate the documents and commit what changed, where the target declares the step."""
        if not self._runs(ProjectStep.DOCS):
            return
        self.step = MESSAGES.roadmap.implement_step_names["docs"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "docs", "generate", "--sync-readme"])
        self._commit_if_changed(f"docs: regenerate the documentation (#{self.number})")

    def _finish_change(self) -> None:
        names = MESSAGES.roadmap.implement_step_names
        self._generate_docs()
        change = self._active_change()
        if change is None or not self._runs(ProjectStep.ARCHIVE):
            return
        self.step = names["archive"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "openspec", "archive", change.name])
        self._commit_if_changed(f"docs(openspec): archive the change (#{self.number})")

    def _push(self) -> int:
        """Rebase onto the default branch again, then push with a lease on the remote tip that the
        job has seen, so a push of anyone else is never overwritten. A Planned item has no remote
        tip yet: its first push publishes the branch. The job skips the checks at a head that
        `implement.checked_sha` holds and the push at a head that `implement.published_sha` holds,
        and writes each mark when its phase passes, so a Job that was killed does not repeat it
        (#4070). The number of the pull request."""
        self.step = MESSAGES.roadmap.implement_step_names["push"]
        self._sync()
        if self.checked_sha != self._head():
            with observe_implement(self.repo, StepName.CHECKS):
                self._scoped_checks()
            self.checked_sha = self._head()
            self.store.set_marks(self._fresh(), {ImplementRecordKey.CHECKED_SHA: self.checked_sha})
        self.step = MESSAGES.roadmap.implement_step_names["push"]
        if self.pull is not None and self.published_sha == self._head():
            return self.pull
        with observe_implement(self.repo, StepName.PUBLISH):
            if self.pull is None:
                pull = self._publish()
            else:
                self._push_with_lease()
                pull = self.pull
        self.published_sha = self._head()
        self.store.set_marks(self._fresh(), {ImplementRecordKey.PUBLISHED_SHA: self.published_sha})
        return pull

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
        for result in results:
            self.trace.check(result.command, result.status)
        return next((result for result in results if not result.passed), None)

    def _scoped_checks(self) -> None:
        """Run the checks a person runs before a push (#3043), and give a failed check to a fix
        step, at most `roadmap.implement.repair_rounds` times. The documents are generated again
        after each fix, because a fix can change a command or an option. The job pushes a finished
        item only after they pass. A stop in this phase pushes the commits that passed, as any other
        stop does, an error or a command that ran out of time too (#3645): the finished groups stay
        on `origin`, and the pull request stays a draft. Raises `_StopError`."""
        try:
            self._scoped_rounds()
        except _StopError as stop:
            stop.kept_branch = True
            raise
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError, subprocess.TimeoutExpired) as exc:
            raise _error_stop(self.step, exc, kept_branch=True) from exc

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
                raise _StopError(
                    self.step,
                    reason,
                    check=failed.name,
                    check_log=failed.log,
                    repair_rounds=budget,
                )
            self._fix(failed.name, failed.log)
            self._generate_docs()

    def _push_with_lease(self, tip: str | None = None) -> None:
        """Push `tip` (the head by default) with a lease on the remote tip that the job has seen."""
        tip = tip or self._head()
        remote = self._git("rev-parse", f"origin/{self.branch}")
        if remote != tip:
            self._git(
                "push", f"--force-with-lease={self.branch}:{remote}", "origin", self._refspec(tip)
            )

    def _refspec(self, tip: str) -> str:
        """The source of a push: the branch, or the commit `tip` when it is no head of the
        checkout."""
        return self.branch if tip == self._head() else f"{tip}:refs/heads/{self.branch}"

    def _current_tip(self, *, in_step: bool) -> str:
        """The commit to push, which holds `origin/<default>` as far as a rebase allows (#4380). A
        run takes minutes, and the default branch moves in that time. Between steps and at a stop
        the checkout is clean, so the job rebases it as `_sync` does. A step that runs holds the
        shas of its `wip:` commits and may hold edits, so `_rebased_copy` rebases a copy and leaves
        the checkout alone. A conflict aborts the rebase and goes to the log: the push goes on with
        the head, so that the work stays on `origin`, and the sync of `_push` stops the item with
        the same conflict."""
        try:
            if in_step:
                return self._rebased_copy()
            self._sync()
            self._move_wip()
        except _StopError as conflict:
            print_muted(conflict.reason.strip(), to_stderr=True, safe=True)
        return self._head()

    def _move_wip(self) -> None:
        """Record the last `wip:` commit again after a rebase rewrote it."""
        if self.wip is None:
            return
        if kept := kept_commits(self._git, f"origin/{self.default}"):
            self.wip = replace(self.wip, sha=kept[0])

    def _rebased_copy(self) -> str:
        """The tip of the commits of `HEAD` rebased onto `origin/<default>` in a detached worktree
        that goes at once, or `HEAD` when the default branch has no commit that it lacks."""
        self._git("fetch", "-q", "origin", self.default)
        if not self._git("rev-list", "-n", "1", f"HEAD..origin/{self.default}"):
            return self._head()
        folder = Path(tempfile.mkdtemp(prefix="rebase-", dir=self.path.parent))
        copy = folder / "copy"
        try:
            self._git("worktree", "add", "-q", "--detach", str(copy), "HEAD")
            try:
                self._rebase(copy)
                return git(copy, "rev-parse", "HEAD", operation=GIT_OPERATION)
            finally:
                self._git("worktree", "remove", "--force", str(copy))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def _has_new_commits(self) -> bool:
        return self._head() != self._git("rev-parse", f"origin/{self.default}")

    def _publish(self, tip: str | None = None) -> int:
        """The first push of a Planned item: push the new branch with `-u`, open its draft pull
        request, and record both. The first body already closes the delivered issue, so a stop
        leaves a grounded draft (#3273); the final body comes after the archive. A draft that GitHub
        refuses takes the branch off `origin` again, so no branch stays without a pull request, and
        stops the item with nothing left to push."""
        texts = MESSAGES.roadmap
        title = self._delivery_title()
        self._git("push", "-u", "origin", self._refspec(tip or self._head()))
        try:
            created = get_github_session().client.create_draft_pull(
                self.repo,
                title=title,
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
        `.github/labels.yml` declares on the default branch and no other (#2800). The check
        `Semantic PR title` counts the summary in UTF-16 units, so a long summary stops the item
        before the job writes a title that the check refuses (#3292)."""
        declared = declared_labels(self.store, ref=None)
        title = delivery_title(self.target.item.title, declared)
        problems = title_problems(title, declared)
        if problems:
            raise _StopError(
                self.step,
                MESSAGES.roadmap.implement_stop_title_refused.format(
                    problems=" ".join(problems), title=title
                ),
                push=False,
            )
        return title

    def _archived_name(self) -> str:
        """The folder `openspec archive` made for the change: `<date>-<issue>-<slug>`."""
        folder = self.path / CONST_OPENSPEC_ARCHIVE_DIR
        pattern = f"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-{self.number}-*"
        return next((p.name for p in sorted(folder.glob(pattern)) if p.is_dir()), "")

    def _why(self, change: str, room: int) -> str:
        """The "why" of the proposal in the folder `change` on one line, at most `room` characters
        long. The title of the item stands in when the proposal has none, when its text is longer
        than `room`, or when it holds a closing keyword for an issue, which would close that issue
        when the pull request merges. The text is never cut: a cut text ends with `...` and reads
        as a mistake."""
        proposal = self.path / change / "proposal.md"
        text = ""
        if proposal.is_file():
            section = section_text(proposal.read_text(encoding="utf-8"), _WHY_HEADINGS)
            text = safe_text(section.partition("\n")[2])
        if not text or len(text) > room or closing_keyword_in(text) is not None:
            text = safe_text(self.target.item.title)
        return text

    def _body(self, change: str) -> str:
        """The body of the pull request, in the form of `pull_form`: the why, `Closes #<issue>` and
        the `Change:` line for the folder `change`. A body that breaks the form stops the item
        before the job writes it."""
        room = BODY_MAX_CHARS - len(f"\n\nCloses #{self.number}\n\nChange: `{change}/`")
        try:
            return build_body(why=self._why(change, room), issue=self.number, change=change)
        except ValidationError as exc:
            problems = " ".join(line.removeprefix("- ") for line in str(exc).splitlines())
            raise _StopError(
                self.step,
                MESSAGES.roadmap.implement_stop_body_refused.format(problems=problems),
                push=False,
            ) from exc

    def _pull_request(self, pull: int) -> None:
        """Set the title and the body of the pull request. The title is the one of the issue: the
        staging pull request of a Staged item has the type `docs(openspec)` (#2714). The body is
        built with `build_body`, so a body that breaks the form stops the item (#3215)."""
        self.step = MESSAGES.roadmap.implement_step_names["pull_request"]
        texts = MESSAGES.roadmap
        archived = self._archived_name()
        active = self._active_change()
        if archived:
            change = f"{CONST_OPENSPEC_ARCHIVE_DIR}/{archived}"
        elif active is not None:
            # A project that declares no archive step keeps the active folder.
            change = f"{CONST_OPENSPEC_CHANGES_DIR}/{active.name}"
        else:
            # No folder: the body has no `Change:` line to name, and the step `ready` stops the
            # item and says that the change is missing.
            return
        body = self._body(change)
        client = get_github_session().client
        before = client.get_pull(self.repo, pull)
        delivery_title = self._delivery_title()
        client.update_pull(self.repo, pull, title=delivery_title, body=body)
        self._comment(pull)
        try:
            declared = declared_labels(self.store, ref=None)
            old = title_labels(before.title, declared)
            new = title_labels(delivery_title, declared)
            add_pull_labels(self.store, pull, new.labels)
            remove_pull_labels(self.store, pull, stale_labels(before.labels, old, new))
        except GitHubUnauthenticatedError:
            raise
        except GitHubOperationError as exc:
            client.comment_on_pull(
                self.repo, pull, texts.implement_pull_labels_failed.format(error=exc)
            )

    def _comment(self, pull: int) -> None:
        """Write the comment of this run on the pull request: the table of the steps of this Job,
        the amendments, the scoped runs and the notes. A run has one comment, that the second line
        marks with the run id (#4070). The first write posts it, and a later write changes it, so a
        repair round shows in the same comment. A Job with nothing to show writes nothing, so a
        rerun does not post an empty comment and does not hide the table of the run before."""
        texts = MESSAGES.roadmap
        table = summary_table(self._row(outcome) for outcome in self.outcomes)
        amend_lines = [amendment.line() for amendment in self.amendments]
        scoped_lines = self._scoped_lines()
        skipped_lines = [
            texts.implement_pull_comment_skipped.format(
                step=step.value, file=CONST_ROADMAP_IMPLEMENT_STEPS_FILE
            )
            for step in self.skipped_steps
        ]
        lines = "\n".join([*amend_lines, *skipped_lines, *scoped_lines, *self._check_lines()])
        body = "\n\n".join(part for part in (table, lines) if part)
        if not body:
            return
        run = texts.implement_pull_comment_run.format(
            run=self.target.item.job_record.get(ImplementRecordKey.JOB) or _MANUAL_RUN
        )
        comment = texts.implement_pull_comment.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, run=run, lines=body
        )
        client = get_github_session().client
        if self.comment_id is None and not self.comments_listed:
            self.comments_listed = True
            head = [CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, run]
            self.comment_id = next(
                (
                    found.id
                    for found in client.list_issue_comments(self.repo, pull)
                    if found.body.splitlines()[:2] == head
                ),
                None,
            )
        if self.comment_id is None:
            self.comment_id = client.comment_on_pull(self.repo, pull, comment)
        else:
            client.update_issue_comment(self.repo, self.comment_id, comment)

    def _check_lines(self) -> list[str]:
        """The lines of the checks of the outcomes (#3042): the fail-to-pass result of
        each behavior group, and the output of each verify command of a group of kind `other`."""
        texts = MESSAGES.roadmap
        lines: list[str] = []
        for outcome in self.outcomes:
            if (replay := outcome.fail_to_pass) is not None:
                lines.append(
                    texts.implement_pull_fail_to_pass.format(
                        group=outcome.group,
                        status=_base_status_text(replay.status),
                        failed=", ".join(replay.failed) or texts.implement_pull_fail_to_pass_none,
                    )
                )
                continue
            lines.extend(
                texts.implement_pull_verified.format(
                    group=outcome.group,
                    command=check.command,
                    status=check.status,
                    fence=code_fence(check.output),
                    output=check.output,
                )
                for check in outcome.verified
            )
        return lines

    def _scoped_lines(self) -> list[str]:
        """One line for each run of a scoped check: its name, its result and its
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
            for result in self.scoped
        ]
        notes = [
            texts.implement_pull_comment_scoped_note.format(note=note) for note in self.scoped_notes
        ]
        return [*runs, *notes]

    def _row(self, outcome: StepOutcome) -> SummaryRow:
        """The row of the table for a step: its attempts are the first turn and the repair
        rounds, and its last failing command is in the trace."""
        step = _outcome_label(outcome)
        return SummaryRow(
            step=step,
            status=outcome.status.value,
            attempts=1 + outcome.repair_rounds,
            tokens_in=outcome.input_tokens,
            tokens_out=outcome.output_tokens,
            command=last_failing_command(self.trace.events, step),
        )

    def _stop_table(self, stop: _StopError) -> str:
        """The table of every step of the run for the stop comment. The step that stopped is in
        it, with the name of the failed check of the pull request when no command failed. A stop
        that has no outcome, as a command of the job, a push or the checks, gets a row of its
        own, with the repair rounds of the stop as its attempts."""
        rows = [self._row(outcome) for outcome in self.outcomes]
        failing = last_failing_command(self.trace.events, stop.step, stop.check)
        if rows and rows[-1].step == stop.step and self.outcomes[-1].status is StepStatus.STOPPED:
            rows[-1] = replace(rows[-1], command=failing)
        else:
            rows.append(
                SummaryRow(
                    step=stop.step,
                    status=StepStatus.STOPPED.value,
                    attempts=1 + stop.repair_rounds,
                    tokens_in=0,
                    tokens_out=0,
                    command=failing,
                )
            )
        return summary_table(rows)

    def _checks(self, pull: int) -> None:
        """Watch the checks. A failed check gets a fix step, a push and a new watch, at most
        `roadmap.implement.repair_rounds` times (#3043). A check that still fails after the last
        round stops the item."""
        self.step = MESSAGES.roadmap.implement_step_names["checks"]
        budget = load_settings().roadmap.implement.repair_rounds
        watch = self._watch(pull)
        rounds = 0
        for _round in range(budget):
            if watch.kind is not WatchKind.FAILED or watch.check is None:
                break
            self._repair_after_push(pull, watch.check)
            rounds += 1
            watch = self._watch(pull)
        if watch.kind is not WatchKind.READY:
            name = watch.check.name if watch.check is not None else ""
            raise _StopError(self.step, watch.reason, check=name, repair_rounds=rounds)

    def _watch(self, pull: int) -> Watch:
        """One watch of the checks, timed as the step `watch`. Any result but ready is an error."""
        with observe_implement(self.repo, StepName.WATCH) as timer:
            watch = watch_pull(self.repo, pull, self._head())
            if watch.kind is not WatchKind.READY:
                timer.fail()
        return watch

    def _repair_after_push(self, pull: int, check: PRCheckItem) -> None:
        """One repair round for the failed check `check` of the pull request: a fix step, the push
        (with the scoped checks), and a comment that shows the round."""
        self._fix(check.name, failed_log(self.repo, check))
        self._push()
        self._comment(pull)
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
            model_for_tier=self.model_for_tier,
            trace=self.trace,
            spend=self._item_spend(),
            recorded_tests=self._recorded_tests(),
        )
        self.outcomes.append(outcome)
        if outcome.status is StepStatus.STOPPED:
            raise _stopped_by(self.step, outcome, check=check, log=log)

    def _ready(self, pull: int) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["ready"]
        client = get_github_session().client
        status = client.get_pull_status(self.repo, pull)
        head = status.head_sha or self._head()
        if not status.head_sha:
            status = status.model_copy(update={"head_sha": head})
        owner, name = self.repo.split("/", 1)
        checks = read_check_runs(owner, name, head)
        archived = self._archived_name()
        if archived:
            tasks_path = self.path / CONST_OPENSPEC_ARCHIVE_DIR / archived / "tasks.md"
            tasks_text = tasks_path.read_text(encoding="utf-8") if tasks_path.is_file() else ""
            change = ChangeFacts(archived=True, tasks_text=tasks_text)
        elif active := self._active_change():
            active_tasks = active / "tasks.md"
            tasks_text = active_tasks.read_text(encoding="utf-8") if active_tasks.is_file() else ""
            change = ChangeFacts(
                archived=False,
                tasks_text=tasks_text,
                archive_required=ProjectStep.ARCHIVE
                in declared_steps(self.path, f"origin/{self.default}"),
            )
        else:
            change = None

        draft = Draft(
            kind=DraftKind.IMPLEMENT,
            pull=status,
            item=self.target.item,
            checks=checks,
            change=change,
        )
        readiness = draft_readiness(draft)
        if readiness.answer is not Answer.READY:
            raise _StopError(self.step, readiness.reason)

        mark_ready(self.repo, pull)
        marks: dict[Any, str | int | None] = {
            ImplementRecordKey.SHA: head,
            ImplementRecordKey.PR: str(pull),
            ImplementRecordKey.SPEND: self._spend(),
            ImplementRecordKey.TRACE: self.trace.encode(),
            ImplementRecordKey.REPAIR_ROUNDS: sum(o.repair_rounds for o in self.outcomes),
            ImplementRecordKey.BASE: None,
            ImplementRecordKey.CHECKED_SHA: None,
            ImplementRecordKey.PUBLISHED_SHA: None,
            ImplementRecordKey.RESULT: ImplementResult.READY.value,
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
        self.store.set_marks(
            self._fresh(), {ImplementRecordKey.RESULT: ImplementResult.YIELDED.value}
        )

    def end_stopped(self, stop: _StopError) -> ImplementResult:
        """End a run that a step stopped. A claim that came while the step ran is the end of the
        run at this boundary: the stop pushes nothing then, opens no pull request and sets no
        Status (#2910)."""
        try:
            self._require_unclaimed(MESSAGES.roadmap.implement_boundary_stop.format(step=stop.step))
        except _ClaimedError as claimed:
            self.yield_to(claimed)
            return ImplementResult.YIELDED
        self.stop(stop)
        return ImplementResult.STOPPED

    # ── The stop ──

    def stop(self, stop: _StopError) -> None:
        """Push what passed, tell the item why, set it Blocked, and record the step."""
        texts = MESSAGES.roadmap
        note = self._push_passed() if stop.push else ""
        if stop.push and not note:
            note = self._kept_note(branch=stop.kept_branch)
        if self.pull is not None and self.amendments:
            self._comment(self.pull)
        last = safe_text(mask_secrets(stop.last_message))[
            :CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS
        ]
        reason = textwrap.indent(
            mask_secrets(stop.reason).strip()[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS], "    "
        )
        klass = (
            stop.failure_class
            if stop.failure_class is not None
            else classify_failure(
                FailureEvidence(
                    text=stop.reason,
                    exit_status=stop.status,
                    check=stop.check,
                    log=stop.check_log,
                )
            )
        )
        check = shown(
            mask_secrets(stop.check or last_failing_command(self.trace.events, stop.step) or ""),
            CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
        )
        check_log = _check_log_end(stop.check_log)
        taken: FailureAction | None = None
        if stop.tier_changes:
            taken = FailureAction.CHANGE_TIER
        elif stop.repair_rounds:
            taken = FailureAction.REPAIR
        elif any(_step_label(a.group) == stop.step for a in self.amendments):
            taken = FailureAction.AMEND
        left = stop.action_left if stop.action_left is not None else left_action(klass, taken)
        print_muted(
            texts.implement_failure_trace.format(
                failure_class=klass.value,
                left=left.value,
            )
        )
        self.store.comment(
            self.number,
            texts.implement_comment_stopped.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
                step=stop.step,
                check=_check_section(check, check_log),
                failure=failure_lines(
                    klass,
                    repair_rounds=stop.repair_rounds,
                    taken=taken,
                    left=left,
                    tier_changes=stop.tier_changes,
                ),
                table=self._stop_table(stop),
                reason=reason,
                last=last or texts.implement_comment_last_none,
                diff=_diff_section(stop),
                note=note,
            ),
        )
        marks: dict[Any, str | int | None] = {
            ImplementRecordKey.STOPPED: stop.step,
            ImplementRecordKey.FAILURE: klass.value,
            ImplementRecordKey.CHECK: check or None,
            ImplementRecordKey.CHECK_LOG: check_log or None,
            ImplementRecordKey.CONFLICT: json.dumps(list(stop.conflict_files))
            if stop.conflict_files
            else None,
            ImplementRecordKey.SPEND: self._spend(),
            ImplementRecordKey.TRACE: self.trace.encode(),
            ImplementRecordKey.REPAIR_ROUNDS: sum(o.repair_rounds for o in self.outcomes)
            + stop.repair_rounds,
        }
        if self.pull is not None:
            marks[ImplementRecordKey.PR] = str(self.pull)
        if self.wip is not None:
            marks[ImplementRecordKey.WIP] = _wip_record(self.wip)
        marks[ImplementRecordKey.RESULT] = ImplementResult.STOPPED.value
        self.store.set_field(
            self._fresh(),
            ItemField.STATUS,
            derive_status(StatusFacts(stopped=True)),
            marks=marks,
        )

    def _push_passed(self, *, in_step: bool = False) -> str:
        """Push the commits of the steps that passed, on a branch that holds the default branch
        (`_current_tip`). A Planned item with a commit publishes its branch and opens its draft;
        with none, nothing is pushed. `in_step` is true for the `wip:` push of a step that runs. The
        text to add to the comment when the push fails, else empty."""
        texts = MESSAGES.roadmap
        try:
            if self.pull is None and not self._has_new_commits():
                return ""
            tip = self._current_tip(in_step=in_step)
            if self.pull is not None:
                self._push_with_lease(tip)
            else:
                self._publish(tip)
        except GitOperationError as exc:
            return texts.implement_stop_push_failed.format(output=mask_secrets(str(exc)))
        except _StopError as exc:
            return texts.implement_stop_push_failed.format(output=mask_secrets(exc.reason))
        return ""


def _earlier_stop(check_log: str | None, conflict: str | None) -> EarlierStop | None:
    """The stop of the earlier Job that the record holds: the end of a check log and the files of
    a rebase conflict as a JSON list (#4071), or None when it holds neither. A list that is no JSON
    list of strings is left out and named on stderr: only a hand edit makes one."""
    files: tuple[str, ...] = ()
    if conflict:
        try:
            files = tuple(TypeAdapter(list[str]).validate_json(conflict))
        except ModelValidationError as error:
            print_muted(
                MESSAGES.roadmap.implement_earlier_stop_bad_files.format(error=error.error_count()),
                to_stderr=True,
                safe=True,
            )
    if not check_log and not files:
        return None
    return EarlierStop(check_log=check_log or "", conflict_files=files)


def _wip_record(commit: WipCommit) -> str:
    """The value of `implement.wip` for a `wip:` commit (#3054)."""
    return json.dumps(
        {"group": commit.group, "done": commit.done, "of": commit.total, "sha": commit.sha}
    )


def _error_stop(step: str, exc: Exception, *, kept_branch: bool = False) -> _StopError:
    """The stop that an error ends the run with: its class and its message, secrets masked."""
    reason = MESSAGES.roadmap.implement_stop_error.format(
        error=type(exc).__name__, message=mask_secrets(str(exc))
    )
    return _StopError(step, reason, kept_branch=kept_branch)


def _implement_item(
    store: RoadmapStore,
    repo: str,
    source: Path,
    target: ImplementTarget,
    *,
    model: Any,
    window: int,
    model_for_tier: Callable[[str], Any] | None = None,
    splitter: Any = None,
) -> ImplementResult:
    """Run one item: how its run ended (`ImplementResult`)."""
    default = default_branch(source, operation=GIT_OPERATION)
    with _worktree(source, target) as path:
        run = _ItemRun(
            store,
            repo,
            path,
            target,
            model,
            window,
            default,
            model_for_tier=model_for_tier,
            splitter=splitter,
        )
        try:
            run.execute()
        except _ClaimedError as claimed:
            run.yield_to(claimed)
            return ImplementResult.YIELDED
        except _StopError as stop:
            return run.end_stopped(stop)
        except AICredentialsError, GitHubUnauthenticatedError:
            raise
        except (DevOpsCLIError, AIClientError, subprocess.TimeoutExpired) as exc:
            return run.end_stopped(_error_stop(run.step, exc))
        if run.returned:
            return ImplementResult.RETURNED
    return ImplementResult.READY


def apply_implement(
    store: RoadmapStore,
    plan: ImplementPlan,
    *,
    source: Path | str,
    model: Any,
    window: int,
    model_for_tier: Callable[[str], Any] | None = None,
    splitter: Any = None,
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
    ended: dict[ImplementResult, list[int]] = {kind: [] for kind in ImplementResult}
    failed: list[ImplementFailure] = []
    for target in plan.selected:
        item = target.item
        try:
            how = _implement_item(
                store,
                plan.repo,
                checkout,
                target,
                model=model,
                window=window,
                model_for_tier=model_for_tier,
                splitter=splitter,
            )
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
        tuple(ended[ImplementResult.READY]),
        tuple(ended[ImplementResult.STOPPED]),
        tuple(failed),
        tuple(ended[ImplementResult.YIELDED]),
        tuple(ended[ImplementResult.RETURNED]),
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


def _base_status_text(status: BaseStatus) -> str:
    """The words that the PR comment uses for the result of a replay on the base commit (#3042)."""
    texts = MESSAGES.roadmap
    words = {
        BaseStatus.FAILS: texts.implement_base_fails,
        BaseStatus.PASSES: texts.implement_base_passes,
        BaseStatus.ERRORS: texts.implement_base_errors,
        BaseStatus.NOT_RUN: texts.implement_base_not_run,
    }
    return words[status]
