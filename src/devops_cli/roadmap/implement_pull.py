"""The calls the implement job makes about its pull request (#2665): the watch of its checks, the
log of a failed check, and `gh pr ready`.

All of them run in the job's own process. The agent's shell never calls them, and holds no
credential for them.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from devops_cli.config.constants import (
    CONST_CI_TEST_JOB_NAME,
    CONST_GH_CLI,
    CONST_OPENSPEC_ARCHIVE_DIR,
    CONST_OPENSPEC_ARCHIVED_FOLDER_RE,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_ROADMAP_IMPLEMENT_HEAD_POLLS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS
from devops_cli.config.settings import load_settings
from devops_cli.core import clock
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git.branch_form import issue_of_branch
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import GitHubClient, PullRequestFile, PullStatus
from devops_cli.github.pr_monitor import PRMonitorResult, monitor_pr
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.run_view import fetch_workflow_run_view
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.store import (
    ImplementRecordKey,
    Item,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.security.sanitizer import mask_secrets

# GitHub's name for a pull request that cannot merge because its branch conflicts with the base.
_CONFLICT_STATES = frozenset({"dirty", "conflicting"})
# The index of the run's number in the path of a check's link, after `runs`: `runs/<run>/job/<job>`.
_JOB_SEGMENT = 2


class DraftKind(StrEnum):
    """The kind of a pull request: stage plan, implement, agent or person."""

    STAGE_PLAN = "stage_plan"
    IMPLEMENT = "implement"
    AGENT = "agent"
    PERSON = "person"


class Answer(StrEnum):
    """The decision of whether a draft pull request is ready for review."""

    READY = "ready"
    WAIT = "wait"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Readiness:
    """The answer to whether a draft pull request is ready, with the reason on wait or refuse."""

    answer: Answer
    reason: str = ""


@dataclass(frozen=True)
class ChangeFacts:
    """What the decision reads about the change folder: whether it is archived, whether the
    target requires the archive (#3484), and its `tasks.md`."""

    archived: bool
    tasks_text: str = ""
    archive_required: bool = True


@dataclass(frozen=True)
class Draft:
    """What the decision reads about a draft pull request."""

    kind: DraftKind
    pull: PullStatus
    item: Item | None = None
    checks: CheckVerdictSummary | None = None
    change: ChangeFacts | None = None
    declared: bool = False


def kind_of(item: Item | None, pull: int | None = None) -> DraftKind:
    """The kind of pull request: agent, person, implement or stage plan.

    Reads the record, in this order: `owner/agent` gives agent, `owner/human` gives person,
    `implement.pr` equal to the pull request gives implement, `stage.pr` equal to it gives
    stage plan, else person.
    """
    if item is None:
        return DraftKind.PERSON
    if item.owner == "agent" or "owner/agent" in item.labels:
        return DraftKind.AGENT
    if item.owner == "human" or "owner/human" in item.labels:
        return DraftKind.PERSON
    pull_str = str(pull) if pull is not None else None
    if pull_str and item.job_record.get(ImplementRecordKey.PR) == pull_str:
        return DraftKind.IMPLEMENT
    if pull_str and item.job_record.get(StageRecordKey.PR) == pull_str:
        return DraftKind.STAGE_PLAN
    return DraftKind.PERSON


def _judge_completeness(draft: Draft) -> Readiness | None:
    texts = MESSAGES.roadmap
    match draft.kind:
        case DraftKind.STAGE_PLAN:
            return None
        case DraftKind.IMPLEMENT:
            if draft.change is None:
                return Readiness(Answer.REFUSE, texts.draft_change_missing)
            groups = parse_task_groups(draft.change.tasks_text)
            unticked = [g for g in groups if any(not t.ticked for t in g.tasks)]
            if unticked:
                reason = "\n".join(
                    texts.draft_unticked_group.format(number=g.number, title=g.title)
                    for g in unticked
                )
                return Readiness(Answer.REFUSE, reason)
            if draft.change.archive_required and not draft.change.archived:
                return Readiness(Answer.REFUSE, texts.draft_change_not_archived)
            return None
        case DraftKind.AGENT | DraftKind.PERSON:
            if not draft.declared:
                return Readiness(Answer.WAIT, texts.draft_author_not_declared)
            return None


def _check_failure_reason(checks: CheckVerdictSummary) -> str:
    texts = MESSAGES.roadmap
    if checks.unread_count > 0 or bool(checks.unread_reason):
        return checks.unread_reason or texts.implement_stop_checks_unread
    if checks.fail_count > 0:
        first_fail = next(c for c in checks.items if c.bucket == CheckBucket.FAIL)
        return texts.implement_stop_check_failed.format(name=first_fail.name)
    if checks.cancel_count > 0:
        first_cancel = next(c for c in checks.items if c.bucket == CheckBucket.CANCEL)
        return texts.implement_stop_check_failed.format(name=first_cancel.name)
    return texts.implement_stop_checks_unread


def _judge_checks(checks: CheckVerdictSummary) -> Readiness | None:
    texts = MESSAGES.roadmap
    code = checks.exit_code
    if code == 1:
        return Readiness(Answer.REFUSE, _check_failure_reason(checks))
    if code == 8:
        first_pending = next((c for c in checks.items if c.bucket == CheckBucket.PENDING), None)
        name = first_pending.name if first_pending else ""
        reason = (
            texts.draft_check_runs.format(name=name) if name else texts.draft_check_runs_unnamed
        )
        return Readiness(Answer.WAIT, reason)
    return None


def draft_readiness(
    draft: Draft,
    extra_checks: Sequence[Callable[[Draft], Readiness]] = (),
) -> Readiness:
    """One function decides when any draft pull request is ready for review (#2916).

    Completeness is checked first, then check runs when given, then each extra check.
    """
    completeness = _judge_completeness(draft)
    if completeness is not None:
        return completeness

    if draft.checks is not None:
        checks_outcome = _judge_checks(draft.checks)
        if checks_outcome is not None:
            return checks_outcome

    for extra_check in extra_checks:
        outcome = extra_check(draft)
        if outcome.answer is not Answer.READY:
            return outcome

    return Readiness(Answer.READY)


def _find_tasks_path(files: Sequence[PullRequestFile], issue: int) -> tuple[str, bool] | None:
    """Find the path of tasks.md in the pull request's files and whether it is archived."""
    for changed in files:
        match = re.fullmatch(CONST_OPENSPEC_ARCHIVED_FOLDER_RE, changed.filename)
        if match and int(match.group("issue")) == issue:
            date = match.group("date")
            change = match.group("change")
            return f"{CONST_OPENSPEC_ARCHIVE_DIR}/{date}-{change}/tasks.md", True
    for changed in files:
        match = re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, changed.filename)
        if match and int(match.group("issue")) == issue:
            change = match.group("change")
            return f"{CONST_OPENSPEC_CHANGES_DIR}/{change}/tasks.md", False
    return None


def read_draft(
    repo: str,
    number: int,
    *,
    pull: PullStatus | None = None,
    checks: CheckVerdictSummary | None = None,
    declared: bool = False,
    store: RoadmapStore | None = None,
    client: GitHubClient | None = None,
) -> Draft:
    """Read a draft pull request and its context for draft_readiness."""
    if client is None:
        client = get_github_session().client
    if pull is None:
        pull = client.get_pull_status(repo, number)

    issue = issue_of_branch(pull.head_ref)
    if issue is None:
        return Draft(
            kind=DraftKind.PERSON,
            pull=pull,
            item=None,
            checks=checks,
            change=None,
            declared=declared,
        )

    store = store or roadmap_store.get_roadmap_store(repo)
    item = store.item(issue)
    kind = kind_of(item, number)
    if kind is not DraftKind.IMPLEMENT:
        return Draft(
            kind=kind,
            pull=pull,
            item=item,
            checks=checks,
            change=None,
            declared=declared,
        )

    files = client.get_pull_files(repo, number)
    found = _find_tasks_path(files, issue)
    if found is not None:
        tasks_path, archived = found
        tasks_text = client.get_file_at(repo, tasks_path, pull.head_sha) or ""
        change = ChangeFacts(archived=archived, tasks_text=tasks_text)
    else:
        change = None

    return Draft(
        kind=kind,
        pull=pull,
        item=item,
        checks=checks,
        change=change,
        declared=declared,
    )


class WatchKind(StrEnum):
    """What the watch found: every check passed, a check failed, or something else stops the
    item."""

    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class Watch:
    """The result of watching a pull request. `reason` says why the item stops or the check failed,
    and `check` is the first failed check."""

    kind: WatchKind
    reason: str = ""
    check: PRCheckItem | None = None


def _first_failure(failing: Sequence[PRCheckItem]) -> PRCheckItem:
    """The failed check whose log holds the cause. The join check `Tests & Coverage` fails when a
    test shard failed, and its log holds no test output (#3050). A failed shard check is the one
    to read then."""
    shard_prefix = f"{CONST_CI_TEST_JOB_NAME} (shard "
    for check in failing:
        if check.name.startswith(shard_prefix):
            return check
    return failing[0]


def _judge(result: PRMonitorResult) -> Watch:
    """The watch's verdict on a settled status: the checks first, then the threads, then the
    mergeability. A draft and a blocked merge state are not reasons to stop: a person approves
    the pull request later."""
    texts = MESSAGES.roadmap
    status = result.status
    if status.merged:
        return Watch(WatchKind.STOPPED, texts.implement_stop_merged)
    if result.exit_code == 3 or status.pending_checks:
        reason = texts.implement_stop_checks_timeout.format(
            seconds=load_settings().roadmap.implement.monitor_timeout_seconds
        )
        return Watch(WatchKind.STOPPED, reason)
    if status.checks_failed:
        failing = status.failing_checks
        if not failing:
            return Watch(WatchKind.STOPPED, texts.implement_stop_checks_unread)
        first = _first_failure(failing)
        reason = texts.implement_stop_check_failed.format(name=first.name)
        return Watch(WatchKind.FAILED, reason, first)
    if status.unresolved_threads:
        count = len(status.unresolved_threads)
        return Watch(WatchKind.STOPPED, texts.implement_stop_threads.format(count=count))
    if status.mergeable is False or status.mergeable_state in _CONFLICT_STATES:
        return Watch(WatchKind.STOPPED, texts.implement_stop_conflict)
    return Watch(WatchKind.READY)


def watch_pull(repo: str, pull: int, head: str) -> Watch:
    """Watch pull request `pull` of `repo` until the checks of its head `head` settle.

    Right after a push GitHub can still show the old head, with the checks of the old head. A
    status is a result only when its head is `head`; else the watch reads again,
    `CONST_ROADMAP_IMPLEMENT_HEAD_POLLS` times at most. The monitor itself waits while a check
    runs, or while a head holds no check yet, up to the setting
    `roadmap.implement.monitor_timeout_seconds`.
    """
    owner, name = repo.split("/", 1)
    timeout = load_settings().roadmap.implement.monitor_timeout_seconds
    for _ in range(CONST_ROADMAP_IMPLEMENT_HEAD_POLLS):
        result = monitor_pr(
            owner,
            name,
            pull,
            timeout=timeout,
            interval=DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS,
            settle_timeout=0,
            require_reviews=False,
            commit_statuses=False,
        )
        if result.status.head_sha == head:
            return _judge(result)
        clock.sleep(DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS)
    reason = MESSAGES.roadmap.implement_stop_old_head.format(head=head[:12])
    return Watch(WatchKind.STOPPED, reason)


def failed_log(repo: str, check: PRCheckItem) -> str:
    """The log of the failed run of `check`, with credentials masked. It is what `gh` said when it
    cannot read the log, and empty when the link of the check names no run. The fix step then
    works from the name of the check."""
    parts = PurePosixPath(urlsplit(check.link).path).parts
    if "runs" not in parts:
        return ""
    at = parts.index("runs")
    run = parts[at + 1] if len(parts) > at + 1 else ""
    has_job = len(parts) > at + _JOB_SEGMENT + 1 and parts[at + _JOB_SEGMENT] == "job"
    if not run:
        return ""
    viewed = fetch_workflow_run_view(
        run, log_failed=True, job=parts[at + _JOB_SEGMENT + 1] if has_job else None, repo=repo
    )
    return viewed.stdout if viewed.returncode == 0 else viewed.stderr


def mark_ready(repo: str, pull: int) -> None:
    """Mark the draft pull request `pull` ready for review with `gh pr ready`. Raises
    `RoadmapImplementError` when `gh` fails."""
    done = run_gh([CONST_GH_CLI, "pr", "ready", str(pull), "--repo", repo], check=False)
    if done.returncode != 0:
        output = mask_secrets((done.stderr or done.stdout or "").strip())
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_stop_ready_failed.format(output=output)
        )
