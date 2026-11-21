"""The agent phase of the implement job (#2665, #3702): the run of one item in its clone, from the
rebase to the scoped checks, and the end of the run as data for `publish`.

**The phases.** The job runs each item on three phases (`implement_phases.py`, ADR 0030):
`prepare` and `publish` hold the App token and run no code of the pull request; the agent phase,
which this module holds, has no GitHub credential and makes no GitHub call. `prepare` makes a plain
clone of the issue branch and records the base and the lease. The agent phase rebases, runs the
steps, the documents, the archive and the scoped checks, and gives its outcome to `publish`, which
pushes the commits of the bot, writes the comments and the record, and sets the Status
(`implement_report.py`). `apply_implement` runs the three phases in one process (`--phase all`).

**Where it runs.** The job runs a step only when `roadmap.implement.in_runner` is true. The
step's shell checks the first word of a command and is no security boundary, so the pod of a
runner Job is the sandbox. The job clears the dumpable flag of its own process, so that the shell,
a child of the same user, cannot read the job's environment (#2667). Every `git` command and every
model call of the agent phase runs in this process, never in the agent's shell. The job ends every
process of a step when the step ends.

**One item.** The agent phase rebases the branch onto the tip of the default branch that `prepare`
recorded, and settles each stop of the rebase as a developer does: it skips an archive commit,
which the run makes again, and takes the generated documents and `uv.lock` of the default branch
and makes them again. Another conflict, or a git command of the settle that fails, aborts the
rebase and stops the item with the class `conflict` and the action `wait`, with nothing to push;
the model step for it is #6640. It runs one step for each group that has an unticked
task, regenerates the documentation, archives the change and runs the scoped checks. It writes the
why of the body of the pull request, with one rewrite of the model.

**A stop.** A step that stops, a conflict or a failed command stops the item: the agent phase
drops the files that no commit holds (#4487), and `publish` pushes the commits that passed (also a
stop in the scoped checks, #3645), comments the step, the reason and the last message of the agent,
sets Status Blocked, and records `implement.stopped`. The comment starts with the class of the
failure, the action taken and the action left (`failure.py`, #3065). It does not run the item again
until a clear rule of the Service removes the stop: a person's comment `implement: retry`, a new
runner image (`stop_clear.py`), or, for a Job that ended with no result, a continuation (#3721).

**A claim** (#2910). The Service holds the item with `owner/service` while the Job runs. `prepare`
reads the item before it clones, and `publish` before it writes and again right before the push.
When an agent or a person holds it by then, the job ends the item at once: it pushes nothing,
opens no pull request, comments why, and changes neither the Status nor the owner.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final, NoReturn

from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as ModelValidationError

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.config.commands import BIN_DEVOPS, BIN_GIT, BIN_UV
from devops_cli.config.constants import (
    CONST_EXIT_FAILURE,
    CONST_GITHUB_AGENT_REFUSED_ENV,
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_PRE_COMMIT_COMMIT_STAGE,
    CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_DIFF_CHARS,
    CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_REASON_PATHS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import acts_as_github_app, run_subprocess
from devops_cli.core.process_hardening import adopt_orphans, deny_environment_reads
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitHubUnauthenticatedError,
    RoadmapImplementError,
    SecurityError,
    ServiceStoppingError,
    ToolExecutionError,
)
from devops_cli.exceptions.roadmap import OverWindowError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.project import uses_openspec
from devops_cli.output import print_muted
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.failure import (
    FailureAction,
    FailureClass,
    StepName,
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
from devops_cli.roadmap.implement.implement_comments import StepComments
from devops_cli.roadmap.implement.implement_hooks import (
    commit_stage,
    install_hook_environments,
    trusted_config,
)
from devops_cli.roadmap.implement.implement_limits import BudgetExtension, ItemSpend, new_tokens
from devops_cli.roadmap.implement.implement_scoped_ci import (
    ScopedResult,
    ScopedTests,
    plan_tests,
    run_scoped_checks,
    scoped_checks,
)
from devops_cli.roadmap.implement.implement_shell_policy import shown
from devops_cli.roadmap.phases.rebase import (
    ARCHIVE_MESSAGE,
    archive_change,
    archive_commit,
    rebase_onto,
    unmerged,
)

if TYPE_CHECKING:
    from devops_cli.roadmap.implement.implement_report import StopFacts
from devops_cli.roadmap.implement.implement_step import (
    EarlierStop,
    FixRequest,
    ItemReader,
    StepOutcome,
    StepStatus,
    TierSpend,
    find_change,
    run_fix_step,
    run_step,
)
from devops_cli.roadmap.implement.implement_strength import (
    StrengthReport,
    scoped_result,
    strength_report,
)
from devops_cli.roadmap.implement.implement_trace import (
    ImplementTrace,
)
from devops_cli.roadmap.owner_question import OwnerQuestion, QuestionOption
from devops_cli.roadmap.plan_read import PlanReadError, merged_recorded_tests
from devops_cli.roadmap.premise import false_premises
from devops_cli.roadmap.project_profile import ProjectProfile, ProjectStep, resolve_profile
from devops_cli.roadmap.pull_form import BODY_MAX_CHARS, build_body
from devops_cli.roadmap.pull_retry import GatewayPullBody, RefusedPullReply, retried_body
from devops_cli.roadmap.runner_tools import bootstrap_checkout, checkout_environment
from devops_cli.roadmap.stage.stage_change import (
    closing_keyword_in,
    criteria_section,
    group_text,
    measure_groups,
    safe_text,
)
from devops_cli.roadmap.stage.stage_criteria import StageCriterion, criterion_problems
from devops_cli.roadmap.stage.stage_form import form_problems
from devops_cli.roadmap.stage.stage_paths import StagedTree, path_problems
from devops_cli.roadmap.stage.stage_split import ask_split
from devops_cli.roadmap.step_files import TaskGroup, parse_task_groups, section_text
from devops_cli.roadmap.step_metrics import observe_implement
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ImplementResult,
    RoadmapStore,
)
from devops_cli.security.sanitizer import mask_secrets

_WHY_HEADINGS = frozenset({"why"})
# The message of the commit of the archive. `publish` keeps that commit apart (#3702).
_ARCHIVE_MESSAGE: Final[str] = ARCHIVE_MESSAGE
_SUMMARY_HEADINGS: Final[frozenset[str]] = frozenset({"summary"})
_WHAT_CHANGES_HEADINGS: Final[frozenset[str]] = frozenset({"what changes"})
_DOCS_EXTENSIONS: Final[frozenset[str]] = frozenset({".md"})


def plan_commit_type(paths: Iterable[str], issue_type: str | None) -> str | None:
    """The Conventional Commit type that the changed paths select (#4127). A plan that changes only
    `tests/` uses `test`; only `docs/`, `openspec/` or Markdown files uses `docs`; only
    `.github/workflows/` or `.github/actions/` uses `ci`; any other set keeps the type of the
    issue title."""
    relevant = [
        p for p in paths if not (p == "openspec/changes" or p.startswith("openspec/changes/"))
    ]
    if not relevant or issue_type is None:
        return issue_type
    if all(p.startswith("tests/") for p in relevant):
        return "test"
    if all(
        p.startswith("docs/")
        or p.startswith("openspec/")
        or PurePosixPath(p).suffix in _DOCS_EXTENSIONS
        for p in relevant
    ):
        return "docs"
    if all(
        p.startswith(".github/workflows/") or p.startswith(".github/actions/") for p in relevant
    ):
        return "ci"
    return issue_type


def proposal_summary(text: str | None, section: str = "all") -> str | None:
    """The summary from `text`, the text of a `proposal.md`, or None when there is none: the first
    non-empty line of `## Summary` when `section` is 'summary' or 'all', else the first bullet of
    `## What Changes` when `section` is 'changes' or 'all', else None (#4127). `publish` reads the
    text from the git objects of the new tree (#3702)."""
    if text is None:
        return None
    if section in ("summary", "all") and (sec := section_text(text, _SUMMARY_HEADINGS)):
        body = sec.partition("\n")[2]
        first_line = next((line.strip() for line in body.splitlines() if line.strip()), None)
        if first_line:
            return first_line
    if section in ("changes", "all") and (sec := section_text(text, _WHAT_CHANGES_HEADINGS)):
        body = sec.partition("\n")[2]
        for line in body.splitlines():
            s = line.strip()
            if s.startswith(("- ", "* ")) and (bullet := s[2:].strip()):
                return bullet
    return None


# The run id of the comment on the pull request for a run that no Service started (#4070).
_MANUAL_RUN = "manual"


class _RecordedSpend(BaseModel):
    """The spend that the record `implement.spend` holds, as `JobRun._spend` writes it. A key that
    an older record lacks takes its empty value (#4070). `cache_read_tokens` is the part of
    `input_tokens` that the provider read from its cache, and `new_tokens` is the count of the item
    budget in its unit, the new tokens (#4387). A record that a version before #4387 wrote has no
    `new_tokens`: its input tokens hold cache reads in an unknown share, so its Jobs count none."""

    requests: int = 0
    input_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    new_tokens: int = 0
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


@dataclass(frozen=True)
class ImplementFailure:
    """An item whose run failed in a way that left it alone: the class of the error and why."""

    number: int
    title: str
    error: str
    reason: str = ""


@dataclass(frozen=True)
class ImplementApplied:
    """What a run did: the items it took to a draft pull request with the final title and body
    (#6559), the items it stopped, the items it ended because an agent or a person claimed them
    (#2910), and the items whose stop or finish could not be written."""

    drafted: tuple[int, ...] = ()
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


def _files_lines(files: Sequence[str]) -> str:
    """The paths of `files` as a list of lines, cut to `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
    paths, with the count of the paths that the cut leaves out."""
    lines = [f"- {path}" for path in files[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS]]
    if len(files) > CONST_ROADMAP_IMPLEMENT_REASON_PATHS:
        count = len(files) - CONST_ROADMAP_IMPLEMENT_REASON_PATHS
        lines.append(MESSAGES.roadmap.implement_paths_more.format(count=count).strip())
    return "\n".join(lines)


def _extension_section(steps: Sequence[Mapping[str, Any]]) -> str:
    """The part of a comment that names each step of `steps` that got the one extension of its
    token budget (#4394), with the budgets and the counts that gave it, or empty when no step
    did. `steps` are the steps of the record `implement.spend`, the earlier Jobs included."""
    texts = MESSAGES.roadmap
    lines = []
    for step in steps:
        if not (held := step.get("extension")):
            continue
        extension = BudgetExtension.model_validate(held)
        lines.append(
            texts.implement_extension_step.format(
                step=step.get("step", ""),
                cut=texts.implement_extension_cut if extension.ceiling else "",
                **extension.model_dump(exclude={"ceiling"}),
            )
        )
    return texts.implement_extension_section.format(lines="\n".join(lines)) if lines else ""


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


def _diff_section(stop: _StopError | StopFacts) -> str:
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


def _plan_defect_question(step: str, check: str, url: str) -> OwnerQuestion:
    """The one owner question of a stop of class `plan_defect` (#3077): amend the plan or split the
    item, with the step and its failing check as the evidence. The step asks one question, so the
    run ends after it posts the frame."""
    texts = MESSAGES.roadmap
    evidence = (
        texts.implement_owner_question_evidence.format(step=step, check=check)
        if check
        else texts.implement_owner_question_evidence_none.format(step=step)
    )
    return OwnerQuestion(
        marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
        question=texts.implement_owner_question.format(step=step),
        options=tuple(
            QuestionOption(text=text, result=result)
            for text, result in texts.implement_owner_question_options.items()
        ),
        recommendation=texts.implement_owner_question_recommendation,
        evidence=(evidence, texts.implement_owner_question_item.format(url=url)),
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


def require_agent_runner() -> None:
    """Raise `RoadmapImplementError` unless the process is the agent phase of a runner Job: the
    agent phase holds the model key only, so `roadmap.implement.in_runner` is true and the
    environment holds no App private key and no GitHub token (#2695, #6601)."""
    texts = MESSAGES.roadmap
    if not load_settings().roadmap.implement.in_runner:
        raise RoadmapImplementError(texts.implement_job_runner_refused)
    held = [name for name in CONST_GITHUB_AGENT_REFUSED_ENV if os.environ.get(name, "").strip()]
    if held:
        raise RoadmapImplementError(
            texts.implement_agent_phase_key_refused.format(names=", ".join(sorted(held)))
        )


def _tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES:])


def _step_label(group: int) -> str:
    return MESSAGES.roadmap.implement_step_group.format(group=group)


def _step_spend(outcome: StepOutcome) -> dict[str, Any]:
    """The entry of a step in the record `implement.spend`: its label, the size of its first
    request (#3499), its requests, tokens, repair rounds and the size of its largest request
    (#4587), and the one extension of its token budget when it got one (#4394)."""
    entry: dict[str, Any] = {
        "step": _outcome_label(outcome),
        "first_request_tokens": outcome.first_request_tokens,
        "requests": outcome.requests,
        "input_tokens": outcome.input_tokens,
        "output_tokens": outcome.output_tokens,
        "repair_rounds": outcome.repair_rounds,
        "largest_request_tokens": outcome.largest_request_tokens,
    }
    if outcome.extension is not None:
        entry["extension"] = outcome.extension.model_dump()
    return entry


def _outcome_label(outcome: StepOutcome) -> str:
    """The label of the step that left `outcome`: its group, or the fix of a failed check."""
    return _step_label(outcome.group) if outcome.group else MESSAGES.roadmap.implement_step_fix


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
    """The agent phase of one item in the clone that `prepare` made (#3702): the rebase, the steps,
    the documents, the archive and the scoped checks. It holds no GitHub credential: it reads the
    item from `store`, the item of the inputs, and writes nothing to GitHub. `onto` is the tip of
    the default branch that `prepare` recorded."""

    store: ItemReader
    repo: str
    path: Path
    target: ImplementTarget
    model: Any
    window: int
    default: str
    onto: str = ""
    model_for_tier: Callable[[str], Any] | None = None
    splitter: Any = None
    rewriter: Any = None
    rebase: bool = True
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
    _profile: ProjectProfile | None = field(default=None, init=False, repr=False)
    # The spend of the earlier Jobs of the item, from `implement.spend` (#4070).
    earlier: _RecordedSpend = field(default_factory=_RecordedSpend, init=False)
    # The head that an earlier Job checked (#4070), from the record.
    checked_sha: str | None = field(default=None, init=False)
    # The stop of the earlier Job, which the first step of the run gets once (#4071).
    handoff: EarlierStop | None = field(default=None, init=False)
    # The template of the comment of a return to New and its evidence (#5881): `publish` returns
    # the item.
    returned: str = ""
    evidence: str = ""
    # The why of the body of the pull request, with the rewrite of the model (#3215).
    why: str = ""
    conflict_files: tuple[str, ...] = ()
    # The time at which the run of the item began, for the time limit of the item (#3053).
    started: float = field(default_factory=time.monotonic)
    # The strength report of the new tests of the item (#3051).
    strength: StrengthReport | None = None
    # The comments of the item and the time at which its plan merged, which `prepare` read for the
    # steps of the run (#6167).
    comments: StepComments = field(default_factory=StepComments)

    def __post_init__(self) -> None:
        held = self.target.item.job_record
        if not self.target.retry and (recorded := held.get(ImplementRecordKey.SPEND)):
            self.earlier = _RecordedSpend.model_validate_json(recorded)
        self.checked_sha = held.get(ImplementRecordKey.CHECKED_SHA)

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

    @property
    def profile(self) -> ProjectProfile:
        if self._profile is None:
            self._profile = resolve_profile(self.path, f"origin/{self.default}")
        return self._profile

    def _git(self, *args: str) -> str:
        return git(self.path, *args, operation=GIT_OPERATION)

    def _head(self) -> str:
        return self._git("rev-parse", "HEAD")

    def _item_spend(self) -> ItemSpend:
        """What the steps of this run spent so far, for the budgets of the next step (#3053): the
        new tokens of the earlier Jobs and of the steps of this Job (#4387)."""
        return ItemSpend(tokens=self._new_tokens(), started=self.started)

    def _new_tokens(self) -> int:
        """The new tokens that the record of the earlier Jobs counts, and those of this Job."""
        return self.earlier.new_tokens + sum(new_tokens(o) for o in self.outcomes)

    def _program(self, argv: Sequence[str]) -> None:
        """Run a command of the project in the worktree, outside any agent shell. Raises
        `_StopError` for the current step when it fails or runs out of time."""
        shown = " ".join(argv)
        texts = MESSAGES.roadmap
        limit = load_settings().roadmap.implement.command_timeout_seconds
        try:
            done = run_subprocess(
                list(argv),
                cwd=self.path,
                env=checkout_environment(self.path),
                quiet=True,
                timeout=limit,
            )
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
        if not self._git("status", "--porcelain"):
            return
        config = self._hooks_config()
        if config is not None:
            run = commit_stage(self.path, config)
            if self.trace is not None:
                self.trace.check(
                    f"pre-commit {CONST_PRE_COMMIT_COMMIT_STAGE}",
                    0 if run is None else run.returncode,
                )
            if run is not None:
                reason = MESSAGES.roadmap.implement_stop_hooks_failed.format(
                    stage=CONST_PRE_COMMIT_COMMIT_STAGE, status=run.returncode, output=run.output
                )
                raise _StopError(
                    self.step,
                    reason,
                    status=run.returncode,
                    check=f"pre-commit {CONST_PRE_COMMIT_COMMIT_STAGE}",
                    check_log=run.output,
                )
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
        """Run the item from the rebase to the scoped checks and the why of the body of the pull
        request. Raises `_StopError`."""
        self._start()
        self._groups()
        if self.returned:
            return
        self._finish_change()
        self._checks()
        self.why = self._why()

    def _start(self) -> None:
        self.step = MESSAGES.roadmap.implement_step_names["rebase"]
        record = self.target.item.job_record
        self.handoff = _earlier_stop(
            record.get(ImplementRecordKey.CHECK_LOG), record.get(ImplementRecordKey.CONFLICT)
        )
        self._sync()
        self._bootstrap()
        self._install_hooks()

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

    def _bootstrap(self) -> None:
        """Build the coder environment of the worktree before the first model request: the venv
        of its `uv.lock` with the dev group and its Node packages (#6517). The new branch of a
        Planned item starts at the fetched default branch, so its sync refuses a stale lock
        (`--locked`). A staged branch exists: the bootstrap installs its `uv.lock` as it is and
        writes no lock, and the install of the hook environments locks nothing
        (`uv run --frozen`). So the first step finds a clean worktree, and the agent locks a stale
        lock again in its shell (#6557). A failure stops the item with nothing to push."""
        self.step = MESSAGES.roadmap.implement_step_names["bootstrap"]
        try:
            bootstrap_checkout(self.path, locked=self.target.new_branch is not None)
        except ToolExecutionError as exc:
            raise _StopError(
                self.step, str(exc), push=False, failure_class=FailureClass.CI_INFRA
            ) from exc

    def _install_hooks(self) -> None:
        """Fetch the hook environments before the first model request, so that no network failure
        wastes a step. A failure stops the item with nothing to push (#3043)."""
        self.step = MESSAGES.roadmap.implement_step_names["hooks"]
        config = self._hooks_config()
        failure = install_hook_environments(self.path, config) if config else None
        if failure is not None:
            raise _StopError(self.step, failure, push=False)

    def _sync(self) -> None:
        """Rebase onto the tip of the default branch that `prepare` recorded. It makes no network
        call: the clone of `prepare` holds that commit."""
        if not self.rebase:
            return
        self._rebase(self.path)

    def _rebase(self, path: Path) -> None:
        """Rebase the checkout `path` onto `onto`, the tip of `origin/<default>` that `prepare`
        recorded, and settle each stop as a developer does (`rebase_onto`, #3702): `git rebase
        --skip` for a commit whose every path the run makes again (`skips_archive_commit`), and
        `git checkout --ours` with a new generation for conflicts only in the generated documents
        and `uv.lock`. A rebase that git refuses to start, as in a checkout that holds changes, is
        no conflict: no
        abort runs, and the stop has the class `ci_infra`, as a new Job starts from a new clone
        (#4487). A conflict that the rules do not settle aborts the rebase and raises `_StopError`
        with class `conflict` and the conflicted files (#5615); the model step that settles it is
        #6640."""
        try:
            ended = rebase_onto(
                path,
                self.onto or f"origin/{self.default}",
                self.number,
                self._program,
                docs=self.profile.preset.docs_step,
                operation=GIT_OPERATION,
            )
        except _StopError as stop:
            # A new generation that failed or ran out of time: the rebase is not done, so its
            # tree must not reach `publish`.
            self._abort(path)
            stop.push = False
            raise
        except DevOpsCLIError as exc:
            self._stop_conflict(path, exc)
        if not ended.started:
            raise _StopError(
                self.step,
                MESSAGES.roadmap.implement_stop_rebase_not_started.format(
                    branch=self.default, output=str(ended.error)
                ),
                push=False,
                failure_class=FailureClass.CI_INFRA,
            ) from ended.error
        if ended.error is not None:
            self._stop_conflict(path, ended.error)

    def _abort(self, path: Path) -> str:
        """Abort the rebase: the output of a failed abort, or empty."""
        timeout = load_settings().roadmap.implement.command_timeout_seconds
        aborted = run_subprocess(
            [BIN_GIT, "-C", str(path), "rebase", "--abort"],
            check=False,
            quiet=True,
            timeout=timeout,
        )
        return "" if aborted.returncode == 0 else _tail(aborted.stderr)

    def _stop_conflict(self, path: Path, exc: DevOpsCLIError) -> NoReturn:
        """Abort the rebase at a stop that no rule settles, or whose settle failed, and stop the
        item with the class `conflict` and the conflicted files, with nothing to push. No fix round
        runs, so a person settles it until the model step of #6640."""
        files = [shown(mask_secrets(name)) for name in unmerged(path, operation=GIT_OPERATION)]
        failed = self._abort(path)
        texts = MESSAGES.roadmap
        reason = texts.implement_stop_rebase.format(branch=self.default, output=str(exc))
        if files:
            reason += texts.implement_stop_rebase_files.format(files=_files_lines(files))
        if failed:
            reason += texts.implement_stop_abort_failed.format(output=failed)
        raise _StopError(
            self.step,
            reason,
            push=False,
            failure_class=FailureClass.CONFLICT,
            action_left=FailureAction.WAIT,
            conflict_files=files[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS],
        ) from exc

    def _return_premise(self, request: PlanRequest) -> None:
        self._return_to_new(MESSAGES.roadmap.implement_comment_premise_failed, request.evidence)

    def _check_premise(self, groups: Sequence[TaskGroup]) -> bool:
        """Return the item to New, and say so, when the `Adds:` line of an open behavior group of
        `groups` names an identifier that the branch already defines (#3417, #3453). The line
        alone decides: a group with no `Adds:` line gets no check, and no rule reads the prose of
        a task. The run calls it once, before its first step, so a false premise costs no model
        request and loses no group that passed in the run (#5881). A group whose tasks are all
        ticked passed in an earlier Job, and a group of another kind adds no product identifier,
        so neither gets a check."""
        base = self._head()
        evidence = [
            line
            for group in groups
            if group.is_behavior and not all(task.ticked for task in group.tasks)
            for line in false_premises(self.path, base, group)
        ]
        if not evidence:
            return False
        self._return_to_new(MESSAGES.roadmap.implement_comment_premise_defined, "\n".join(evidence))
        return True

    def _return_to_new(self, template: str, evidence: str) -> None:
        """End the run with a return of the item to New, with a comment of the template `template`
        and `evidence`: `publish` returns the item (#5881)."""
        self.returned = template
        self.evidence = evidence

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
        premise_checked = False

        while True:
            tasks_text = tasks_file.read_text(encoding="utf-8")
            tasks = parse_task_groups(tasks_text)
            group = next((g for g in tasks if not all(task.ticked for task in g.tasks)), None)
            if group is None:
                break
            self.step = _step_label(group.number)
            if not premise_checked:
                premise_checked = True
                if self._check_premise(tasks):
                    return
            try:
                outcome = run_step(
                    self.store,
                    item=self.number,
                    group=group.number,
                    source=self.path,
                    model=self.model,
                    window=self.window,
                    hooks=self._hooks_config(),
                    preset=self.profile.preset,
                    model_for_tier=self.model_for_tier,
                    trace=self.trace,
                    spend=self._item_spend(),
                    recorded_tests=self._recorded_tests(),
                    earlier=self._take_earlier(),
                    comments=self.comments,
                )
            except OverWindowError as err:
                self._handle_over_window(group, err, change, tasks_text, tasks_file, tasks)
                continue
            self.outcomes.append(outcome)
            if outcome.status is StepStatus.STOPPED:
                request = parse_request(outcome.last_message)
                if request is not None:
                    returned = self._handle_request_stop(
                        group.number, request, outcome, tasks_text, tasks_file, amended_groups
                    )
                    if returned:
                        return
                    continue
                raise _stopped_by(self.step, outcome)

    def _take_earlier(self) -> EarlierStop | None:
        """The stop of the earlier Job for the step that runs now, and none for the steps after
        it: the first step either fixes the cause or stops (#4071)."""
        earlier, self.handoff = self.handoff, None
        return earlier

    def _runs(self, step: ProjectStep) -> bool:
        """Whether the job runs `step`: the profile declares it. A step that it does not
        declare is noted for the comment, once (#3484)."""
        preset = self.profile.preset
        if step is ProjectStep.DOCS:
            active = preset.docs_step
        elif step is ProjectStep.ARCHIVE:
            active = bool(
                preset.archive_argv
                and uses_openspec(self.path, f"origin/{self.default}", operation=GIT_OPERATION)
            )
        else:
            active = False
        if active:
            return True
        if step not in self.skipped_steps:
            self.skipped_steps.append(step)
        return False

    def _generate_docs(self) -> None:
        """Generate the documents and commit what changed, where the target declares the step."""
        if not self._runs(ProjectStep.DOCS):
            return
        self.step = MESSAGES.roadmap.implement_step_names["docs"]
        self._program([BIN_UV, "run", BIN_DEVOPS, "docs", "generate"])
        self._commit_if_changed(f"docs: regenerate the documentation (#{self.number})")

    def _finish_change(self) -> None:
        names = MESSAGES.roadmap.implement_step_names
        self._generate_docs()
        change = self._active_change()
        if change is None or not self._runs(ProjectStep.ARCHIVE):
            return
        self.step = names["archive"]
        try:
            archive_change(
                self.path,
                self.number,
                self.profile.preset,
                self._program,
                self._commit_if_changed,
                docs=False,
            )
        except _StopError as stop:
            # An archive that moved the change folder and then exited 1 failed the strict
            # validation of the specs: a spec of the plan is the cause. The output counts specs
            # ("1 failed"), so its words do not decide the class (#4503).
            if (
                stop.status == CONST_EXIT_FAILURE
                and self._active_change() is None
                and self._archived_name()
            ):
                stop.failure_class = FailureClass.PLAN_DEFECT
            raise

    def _scoped_run(self) -> ScopedResult | None:
        """Run the scoped checks for the paths the item changed, and keep their results for the
        comment. The first failed result, or None when every check passed."""
        listed = self._git(
            "diff", "--name-only", "--diff-filter=ACMR", "-z", f"origin/{self.default}", "HEAD"
        )
        changed = [name for name in listed.split("\0") if name]
        tests = (
            plan_tests(self.path, changed)
            if self.profile.preset.test_selection
            else ScopedTests((), "")
        )
        if tests.note and tests.note not in self.scoped_notes:
            self.scoped_notes.append(tests.note)
        checks = scoped_checks(
            self.default, tests.paths, config=self._hooks_config(), preset=self.profile.preset
        )
        results = run_scoped_checks(self.path, checks)
        self.scoped.extend(results)
        for result in results:
            self.trace.check(result.command, result.status)
        if (failed := next((result for result in results if not result.passed), None)) is not None:
            return failed

        tasks_md = ""
        try:
            change = find_change(self.path, self.number, archived=True)
            tasks_file = change / "tasks.md"
            if tasks_file.is_file():
                tasks_md = tasks_file.read_text(encoding="utf-8")
        except RoadmapImplementError:
            tasks_md = ""

        report = strength_report(self.path, tasks_md, changed, self.default, tests.paths)
        self.strength = report
        res = scoped_result(report)
        self.scoped.append(res)
        self.trace.check(res.command, res.status)
        return res if not res.passed else None

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

    def _archived_name(self) -> str:
        """The folder `openspec archive` made for the change: `<date>-<issue>-<slug>`."""
        folder = self.path / CONST_OPENSPEC_ARCHIVE_DIR
        pattern = f"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-{self.number}-*"
        return next((p.name for p in sorted(folder.glob(pattern)) if p.is_dir()), "")

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
            preset=self.profile.preset,
            model_for_tier=self.model_for_tier,
            trace=self.trace,
            spend=self._item_spend(),
            recorded_tests=self._recorded_tests(),
            comments=self.comments,
        )
        self.outcomes.append(outcome)
        if outcome.status is StepStatus.STOPPED:
            raise _stopped_by(self.step, outcome, check=check, log=log)

    def _checks(self) -> None:
        """Run the scoped checks, unless an earlier Job checked this head (`implement.checked_sha`,
        #4070)."""
        if self.checked_sha == self._head():
            return
        with observe_implement(self.repo, StepName.CHECKS):
            self._scoped_checks()

    def _why(self) -> str:
        """The why of the body of the pull request (#3215): the "why" of the proposal on one line,
        or the title of the item when the proposal has none, when it is too long, or when it holds
        a closing keyword. A why that breaks the form of the body gets one rewrite of the model.
        `publish` checks the why again, and builds the body itself. A change with no folder has no
        body, and the step `ready` of `publish` stops the item."""
        archived = self._archived_name()
        active = self._active_change()
        if archived:
            change = f"{CONST_OPENSPEC_ARCHIVE_DIR}/{archived}"
        elif active is not None:
            change = f"{CONST_OPENSPEC_CHANGES_DIR}/{active.name}"
        else:
            return ""
        self.step = MESSAGES.roadmap.implement_step_names["pull_request"]
        room = BODY_MAX_CHARS - len(f"\n\nCloses #{self.number}\n\nChange: `{change}/`")
        proposal = self.path / change / "proposal.md"
        text = ""
        if proposal.is_file():
            section = section_text(proposal.read_text(encoding="utf-8"), _WHY_HEADINGS)
            text = safe_text(section.partition("\n")[2])
        if not text or len(text) > room or closing_keyword_in(text) is not None:
            text = safe_text(self.target.item.title)
        accepted: list[str] = []

        def _build(why: str) -> str:
            body = build_body(why=why, issue=self.number, change=change)
            accepted.append(why)
            return body

        try:
            retried_body(text=text, build=_build, rewrite=self._rewrite())
        except RefusedPullReply as exc:
            raise _StopError(
                self.step,
                MESSAGES.roadmap.implement_stop_body_refused.format(
                    problems=" ".join(exc.problems)
                ),
                failure_class=FailureClass.REFUSED_REPLY,
                push=False,
            ) from exc
        return accepted[-1]

    def _rewrite(self) -> Callable[[str, Sequence[str]], str] | None:
        """The rewrite of a why that breaks the form, from the rewriter of the run."""
        if self.rewriter is None:
            return None
        if hasattr(self.rewriter, "rewrite"):
            return self.rewriter.rewrite  # type: ignore[no-any-return]
        if hasattr(self.rewriter, "chat_structured"):
            return GatewayPullBody(client=self.rewriter).rewrite
        return self.rewriter if callable(self.rewriter) else None

    def archive_commit(self, base: str) -> str | None:
        """The newest archive commit of the item past `base`, or None when the run holds none. The
        archive stays its own commit when `publish` pushes (#3702)."""
        return archive_commit(self.path, base, self.number, operation=GIT_OPERATION)

    # ── The end for a claim ──

    # ── The stop ──

    def _drop_uncommitted(self) -> None:
        """Put the checkout back at its head, before the push of a stop (#4487). A project program
        that failed can leave the files that it wrote, as an archive that moved the change folder
        and then failed the validation of the specs. No commit holds them, so no push sends them,
        and git does not rebase a checkout that holds changes."""
        self._git("reset", "-q", "--hard", "HEAD")
        self._git("clean", "-fdq")


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


def _failure_class_of(exc: Exception) -> FailureClass | None:
    """The class of a stop that `exc` causes, when the error knows it: a command that the process
    runner refuses before it starts (`SecurityError`) is `refused_tool`, as a new runner image meets
    the same refusal (#5887). None lets the classifier read the text."""
    if isinstance(exc, SecurityError):
        return FailureClass.REFUSED_TOOL
    return None


def _error_stop(step: str, exc: Exception, *, kept_branch: bool = False) -> _StopError:
    """The stop that an error ends the run with: its class and its message, secrets masked."""
    reason = MESSAGES.roadmap.implement_stop_error.format(
        error=type(exc).__name__, message=mask_secrets(str(exc))
    )
    return _StopError(step, reason, kept_branch=kept_branch, failure_class=_failure_class_of(exc))


def apply_implement(
    store: RoadmapStore,
    plan: ImplementPlan,
    *,
    source: Path | str,
    model: Any,
    window: int,
    rebase: bool = True,
    model_for_tier: Callable[[str], Any] | None = None,
    splitter: Any = None,
    rewriter: Any = None,
) -> ImplementApplied:
    """Run each selected item of the plan on the three phases in one process (`--phase all`),
    one item after the other. A stopped item does not stop the run, and an item whose writes fail
    is reported while the others still run. Rejected GitHub or model credentials stop the run.
    Raises `RoadmapImplementError` before anything runs unless the process is a runner Job for
    the plan's repository (`require_runner`). It then makes its own process unreadable by the shell
    of an agent, which runs as the same user (`deny_environment_reads`), and adopts the orphans of a
    step (`adopt_orphans`). `prepare` makes a new clone for each item, so `source`, the clone of the
    plan, holds no work of an agent."""
    from devops_cli.roadmap.implement.implement_phases import AgentTools, implement_round

    require_runner(plan.repo)
    deny_environment_reads()
    adopt_orphans()
    del source
    tools = AgentTools(model, window, model_for_tier, splitter, rewriter, rebase)
    ended: dict[ImplementResult, list[int]] = {kind: [] for kind in ImplementResult}
    failed: list[ImplementFailure] = []
    for target in plan.selected:
        item = target.item
        try:
            how = implement_round(store, plan.repo, target, tools)
        except AICredentialsError, GitHubUnauthenticatedError, ServiceStoppingError:
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
        tuple(ended[ImplementResult.DRAFTED]),
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
