"""The status-lane row `watch`: one row watches open plan and delivery pull requests,
batches status queries via GraphQL with REST fallback during quota holds, maintains a
ledger with 30-minute failed-head backoff, and routes lifecycle steps (ADR 0021, section 8; #5024).

A live unit holds a pull request: a runner Job that no round reported (`job_holds`), or the
check-out of a stage Job. The record keeps the name of a runner Job that ended, so that name alone
holds nothing. After the ledger is written, the row runs the fix-checks units of the repository:
it starts a fix Job for each bot pull request that `due_steps` routes to `fix_checks`, and reports
the fix Jobs that ended (`fix_checks_row.py`, #5027). A Kubernetes or a configuration error stops
only that round: the row logs and counts it and gives its result (#6018). A delivery draft that a
fix Job repaired, or whose implement Job ended at the draft (#6559), and whose checks pass gets
the ready path of the step `fix-checks` once for each head, and only the ready path: a check that
fails between the two reads gives `skipped`. The row leaves a delivery draft whose implement Job
stopped. A delivery draft (`_delivery_draft`) whose failed or cancelled check, or conflict, has no
repair owner stops its item, once, through the stop flow of the implement Job: Status Blocked,
`implement.stopped`, the class, `implement.result` stopped, and one stop comment that names the
check or the conflict (#6559). A unit owns a failed check only in mode `on`, for a class in
FIX_CHECK_CLASSES, while the unit of the head and the check has not ended with no repair. The row
judges the latest run of each check name (#5383). A green plan draft is marked ready only
when `draft_readiness` answers ready for the draft that `read_ready_draft` reads. The record can
hold one pull request as the plan and as the delivery of its item, and `read_draft` then judges it
as the delivery, so a task that is not ticked keeps it a draft; the row judges a refused head once
(#6123).

A pull request is the plan of an item only when the record of the item names its number and its
head branch (`recorded_plan`, #7347). The GraphQL read gives the head branch of each open pull
request. The REST round and the read of the plans that are no more open read the pull request
first, and write for the item only when the head branch is the recorded branch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, Field
from pydantic import ValidationError as MalformedRecordError

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import (
    ConfigurationError,
    GitHubNotAnIssueError,
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    RoadmapRunError,
)
from devops_cli.exceptions.k8s import KubernetesError
from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    PRCheckItem,
    _resolve_bucket,
    latest_run_of_each_check,
    no_checks_reported,
    read_check_runs,
)
from devops_cli.github.client import PullStatus
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import (
    FailureClass,
    FailureEvidence,
    classify_failure,
    failure_lines,
    left_action,
)
from devops_cli.roadmap.fix_checks_row import (
    FixChecksRound,
    FixDue,
    round_failed,
    run_fix_checks_round,
)
from devops_cli.roadmap.implement.implement_pull import Answer
from devops_cli.roadmap.jev_completeness import (
    CompletenessOutcome,
    check_completeness,
    completeness_note,
)
from devops_cli.roadmap.release_feed import closing_numbers
from devops_cli.roadmap.stage.stage_criteria import acceptance_criteria
from devops_cli.roadmap.status_sync import (
    StatusFacts,
    facts_of,
    job_holds,
    sync_status,
    write_status,
)
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.fix_checks import (
    has_owner_label,
    run_fix_checks,
    takes_ready_path,
    unit_ended,
)
from devops_cli.roadmap.steps.ready import draft_readiness, mark_ready, read_ready_draft
from devops_cli.roadmap.steps.watch import (
    DueStep,
    PRVerdict,
    WatchState,
    WatchVerdict,
    due_steps,
    fix_checks_check,
    unrepaired_check,
    verdict,
)
from devops_cli.roadmap.stores.store import (
    FixChecksRecordKey,
    FixChecksResult,
    GitHubState,
    ImplementRecordKey,
    ImplementResult,
    Item,
    RoadmapStore,
    StageRecordKey,
    recorded_plan,
)
from devops_cli.telemetry.instruments import ROADMAP_CONFLICTED_PULLS, emit

logger = logging.getLogger(__name__)

_HEAD_CHARS = 12

_OPEN_ROADMAP_PULLS_QUERY: Final[str] = """
query OpenRoadmapPulls($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 100, after: $cursor) {
      nodes {
        number
        title
        body
        isDraft
        mergeable
        headRefOid
        headRefName
        baseRefName
        author {
          login
        }
        labels(first: 20) {
          nodes {
            name
          }
        }
        commits(last: 1) {
          nodes {
            commit {
              oid
              message
              statusCheckRollup {
                state
                contexts(first: 100) {
                  nodes {
                    __typename
                    ... on CheckRun {
                      name
                      status
                      conclusion
                      startedAt
                      completedAt
                    }
                    ... on StatusContext {
                      context
                      state
                    }
                  }
                }
              }
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


class WatchLedgerEntry(BaseModel):
    """The cached state and backoff for one pull request."""

    head: str
    verdict: str
    next_read_at: str | None = None
    base: str = "main"
    commented_head: str | None = None
    ready_head: str | None = None


class WatchLedger(BaseModel):
    """The watch row's ledger beside schedule.json (watch.json)."""

    pulls: dict[int, WatchLedgerEntry] = Field(default_factory=dict)

    @classmethod
    def read(cls, path: Path) -> WatchLedger:
        """Read ledger at path; returns empty ledger if missing."""
        if not path.exists():
            return cls()
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, MalformedRecordError) as exc:
            reason = str(exc).splitlines()[0][:200]
            raise RoadmapRunError(
                f"The watch ledger {path} can't be read ({reason})",
                details={"path": str(path)[:256]},
            ) from exc

    def write(self, path: Path) -> None:
        """Write ledger to path atomically."""
        from devops_cli.output.file_writer import write_json_file

        write_json_file(path, self.model_dump(mode="json"), indent=2, atomic=True)


@dataclass(frozen=True)
class WatchRoundResult:
    """Outcome of one round of the watch row."""

    watched: int = 0
    marked_ready: tuple[int, ...] = ()
    commented_conflicts: tuple[int, ...] = ()
    failed_heads: tuple[int, ...] = ()
    requests_sent: int = 0
    fix_checks: FixChecksRound = field(default_factory=FixChecksRound)


def _latest_contexts(contexts_nodes: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The nodes of the rollup with only the latest run of each check name. Each event of a pull
    request starts its checks in a new suite, so the rollup can hold an old cancelled run beside
    the newer run that replaced it; the REST read keeps the latest run alone, by the same rule
    (`latest_run_of_each_check`, #5383). A StatusContext node stays: the rollup holds the latest
    status of each context."""
    runs = [
        {
            "name": node.get("name"),
            "started_at": node.get("startedAt"),
            "completed_at": node.get("completedAt"),
            "index": index,
        }
        for index, node in enumerate(contexts_nodes)
        if node.get("__typename") == "CheckRun"
    ]
    kept = {run["index"] for run in latest_run_of_each_check(runs)}
    return [
        node
        for index, node in enumerate(contexts_nodes)
        if node.get("__typename") != "CheckRun" or index in kept
    ]


def _parse_contexts(contexts_nodes: Sequence[Mapping[str, Any]]) -> list[PRCheckItem]:
    """Parse GraphQL CheckRun and StatusContext nodes into PRCheckItems, the latest run of each
    check name only (`_latest_contexts`)."""
    items: list[PRCheckItem] = []
    for node in _latest_contexts(contexts_nodes):
        name = node.get("name") or node.get("context") or ""
        status = str(node.get("status") or "").lower()
        conclusion = str(node.get("conclusion") or "").lower()
        state = str(node.get("state") or "").lower()
        bucket, state_str = _resolve_bucket(state, conclusion, status)
        items.append(PRCheckItem(name=name, state=state_str, bucket=bucket))
    return items


def _parse_mergeable(raw: Any) -> tuple[bool | None, str]:
    """Normalize GraphQL or REST mergeable state."""
    if isinstance(raw, bool):
        return raw, "clean" if raw else "dirty"
    if isinstance(raw, str):
        val = raw.upper()
        if val in ("MERGEABLE", "CLEAN"):
            return True, "clean"
        if val in ("CONFLICTING", "DIRTY"):
            return False, "dirty"
        if val == "BEHIND":
            return True, "behind"
    return None, "unknown"


def _graphql_on_hold() -> bool:
    """Whether the GraphQL quota is on hold (below budget floor)."""
    quota = get_github_rate_limiter().get_quota("graphql")
    return quota.is_valid() and (quota.remaining or 0) < DEFAULT_GH_GRAPHQL_BUDGET_FLOOR


def _delivers_an_item(
    store: RoadmapStore, body: str, base_ref: str, default_branch: str
) -> Item | None:
    """Whether a pull request into default_branch closes exactly one open Item."""
    if base_ref != default_branch:
        return None
    closed = closing_numbers(body)
    if len(closed) != 1:
        return None
    item = store.item(closed[0])
    if item is not None and item.state is GitHubState.OPEN:
        return item
    return None


def _is_plan_of(item: Item, pull_number: int, head_ref: str | None) -> bool:
    """Whether pull request `pull_number`, whose head branch is `head_ref`, is the plan of `item`:
    the record of the item names the number and the branch (`recorded_plan`)."""
    plan = recorded_plan(item)
    return plan is not None and plan.is_pull(pull_number, head_ref)


def _find_plan_item(store: RoadmapStore, pull_number: int, head_ref: str | None) -> Item | None:
    """The open item whose plan is pull request `pull_number` with the head branch `head_ref`.
    The recorded branch names its item, so at most one item has the plan."""
    for item in store.items():
        if item.state is GitHubState.OPEN and _is_plan_of(item, pull_number, head_ref):
            return item
    return None


def _jev_holds(
    store: RoadmapStore, repo: str, item: Item, number: int, head: str, base_ref: str
) -> bool:
    """Whether Jev completeness check holds this plan draft."""
    if not load_settings().roadmap.stage.jev_completeness:
        return False
    mark = item.job_record.get(StageRecordKey.JEV) or ""
    if mark == f"{head}:{CompletenessOutcome.HELD}":
        return True
    client = get_github_session().client
    diff = client.get_compare_diff(repo, base_ref, head)
    result = check_completeness(acceptance_criteria(item.body), diff, "plan")
    if not result.holds:
        if mark:
            store.set_marks(item, {StageRecordKey.JEV: None})
        return False
    error_mark = f"{head}:{CompletenessOutcome.ERROR}"
    if not (result.outcome is CompletenessOutcome.ERROR and mark == error_mark):
        post(
            Target(repo, number, client=client),
            CONST_ROADMAP_STAGE_COMMENT_MARKER,
            f"jev-{head}",
            completeness_note(result, number),
        )
    store.set_marks(item, {StageRecordKey.JEV: f"{head}:{result.outcome}"})
    return True


def _read_open_pulls_graphql(owner: str, name: str) -> list[dict[str, Any]]:
    """Read open pull requests via one or paginated GraphQL queries."""
    client = get_github_session().client
    cursor: str | None = None
    all_nodes: list[dict[str, Any]] = []
    while True:
        variables = {"owner": owner, "name": name, "cursor": cursor}
        reply = client.graphql(_OPEN_ROADMAP_PULLS_QUERY, variables)
        repo_data = reply.get("data", {}).get("repository", {})
        pr_conn = repo_data.get("pullRequests", {})
        nodes = pr_conn.get("nodes", [])
        if isinstance(nodes, list):
            all_nodes.extend(nodes)
        page_info = pr_conn.get("pageInfo", {})
        if page_info.get("hasNextPage") and page_info.get("endCursor"):
            cursor = page_info["endCursor"]
        else:
            break
    return all_nodes


@dataclass
class _WatchContext:
    store: RoadmapStore
    repo: str
    current_time: datetime
    recorded_pulls: dict[int, WatchLedgerEntry]
    marked_ready: list[int]
    commented_conflicts: list[int]
    failed_heads: list[int]
    fix_due: list[FixDue] = field(default_factory=list[FixDue])
    total_conflicted: int = 0
    watched_count: int = 0


def _failed_head_in_backoff(
    ctx: _WatchContext,
    pr_number: int,
    head_sha: str,
    base_ref: str,
) -> bool:
    """Count and record `pr_number` and return True when its failed head is in backoff (#6004)."""
    entry = ctx.recorded_pulls.get(pr_number)
    if (
        entry is not None
        and entry.verdict == PRVerdict.FAILED.value
        and entry.head == head_sha
        and entry.base == base_ref
        and entry.next_read_at
        and ctx.current_time < datetime.fromisoformat(entry.next_read_at)
    ):
        ctx.watched_count += 1
        ctx.failed_heads.append(pr_number)
        return True
    return False


def _evaluate_pull(
    ctx: _WatchContext,
    *,
    pr_number: int,
    item: Item,
    is_plan: bool,
    head_sha: str,
    base_ref: str,
    is_draft: bool,
    mergeable: bool | None,
    mergeable_state: str,
    author: str,
    checks: CheckVerdictSummary,
    commit_message: str | None = None,
    labels: tuple[str, ...] = (),
) -> None:
    """Evaluate one roadmap pull request and apply lifecycle steps. `labels` are the labels of the
    pull request: a verdict label other than `verdict/mergeable` holds the ready mark (#6024)."""
    if _failed_head_in_backoff(ctx, pr_number, head_sha, base_ref):
        return

    ctx.watched_count += 1
    has_live_unit = job_holds(item) or bool(item.job_record.get(StageRecordKey.JOB))
    entry = ctx.recorded_pulls.get(pr_number)

    if mergeable is False and not is_draft and not is_plan:
        ctx.total_conflicted += 1

    is_bot = is_plan or (author.endswith("[bot]") if author else False)
    delivery = is_draft and _delivery_draft(item, pr_number, labels)
    stopped = _stopped_delivery(item, pr_number)
    settings = load_settings().roadmap

    state = WatchState(
        pull=pr_number,
        head_sha=head_sha,
        draft=is_draft,
        base_ref=base_ref,
        mergeable=mergeable,
        mergeable_state=mergeable_state,
        commit_message=commit_message,
        checks=checks,
        author=author,
        is_bot=is_bot,
        is_plan=is_plan,
        has_live_unit=has_live_unit,
        labels=labels,
        delivery=delivery,
        repairs=settings.fix_checks.mode == "on",
        ended_checks=_ended_checks(
            item, pr_number, head_sha, checks, settings.implement.continuations_per_item
        )
        if delivery
        else frozenset(),
        stopped=stopped,
    )

    v = verdict(state)
    steps = due_steps(state)
    if DueStep.FIX_CHECKS in steps and (check := fix_checks_check(state)) is not None:
        units = item.job_record.get(FixChecksRecordKey.UNITS)
        ctx.fix_due.append(FixDue(pr_number, head_sha, check, item.number, units))
    if DueStep.STOP in steps and v is not None:
        _stop_unowned_draft(ctx, item, state, v)

    if v is not None:
        if v.verdict is PRVerdict.FAILED:
            ctx.failed_heads.append(pr_number)
            next_read_iso = (ctx.current_time + timedelta(minutes=30)).isoformat()
        else:
            next_read_iso = None

        ctx.recorded_pulls[pr_number] = WatchLedgerEntry(
            head=head_sha,
            verdict=v.verdict.value,
            next_read_at=next_read_iso,
            base=base_ref,
            commented_head=entry.commented_head if entry else None,
            ready_head=entry.ready_head if entry else None,
        )

    _apply_due_steps(
        ctx,
        pr_number=pr_number,
        item=item,
        is_plan=is_plan,
        is_draft=is_draft,
        head_sha=head_sha,
        base_ref=base_ref,
        steps=steps,
        entry=entry,
        checks=checks,
        labels=labels,
    )


def _delivery_draft(item: Item, pull: int, labels: Sequence[str]) -> bool:
    """Whether the draft `pull` is the delivery draft of `item` that the row hands off (#6559):
    the record names it as `implement.pr`, the ready path takes it (`takes_ready_path`: its
    implement Job ended at the draft or a fix Job repaired it, and no stop holds the item), and no
    owner label on the pull request or the item claims it, as the step `fix-checks` reads a claim.
    The record decides, not the kind of the pull request: a Staged item can deliver on its plan
    pull request."""
    return (
        item.job_record.get(ImplementRecordKey.PR) == str(pull)
        and takes_ready_path(item)
        and not has_owner_label(labels)
        and not has_owner_label(item.labels)
    )


def _stopped_delivery(item: Item, pull: int) -> bool:
    """Whether `pull` is the `implement.pr` of an item that holds a stop (#6559). A person owns
    such a draft until `implement: retry` clears the stop: it gets no fix-checks unit and no ready
    mark, as `takes_ready_path` reads the stop."""
    record = item.job_record
    return record.get(ImplementRecordKey.PR) == str(pull) and bool(
        record.get(ImplementRecordKey.STOPPED)
    )


def _ended_checks(
    item: Item, pull: int, head: str, checks: CheckVerdictSummary, extra: int
) -> frozenset[str]:
    """The checks of head `head` whose fix-checks unit ended with no repair (`unit_ended`)."""
    return frozenset(
        check.name
        for check in checks.items
        if unit_ended(item.job_record, pull, head, check.name, extra)
    )


def _stop_unowned_draft(
    ctx: _WatchContext, item: Item, state: WatchState, found: WatchVerdict
) -> None:
    """Stop the item of a delivery draft that no actor takes (#6559). A failed or cancelled check
    or a conflict has a repair owner only when mode `on` lets a fix-checks unit repair, the class
    of the check is one of FIX_CHECK_CLASSES, and the unit of the head and the check has not ended
    with no repair; `due_steps` gives `stop` in each other case. The implement Job ended at the
    draft, so the item takes the stop flow that the Job gave it before: one stop comment that
    names the check or the conflict, Status Blocked, `implement.stopped`, the class and
    `implement.result` stopped. The stop holds the item, so the ready path no longer takes the
    draft (`takes_ready_path`) and the row stops it once."""
    texts = MESSAGES.roadmap
    check: str | None = None
    if found.verdict is PRVerdict.CONFLICT:
        klass = FailureClass.CONFLICT
        reason = texts.watch_stop_conflict.format(pull=state.pull, base=state.base_ref)
    else:
        check = unrepaired_check(state)
        klass = _stop_class(state, check)
        reason = texts.watch_stop_check.format(pull=state.pull, check=check)
    left = left_action(klass, None)
    step = texts.implement_step_names["pull_request"]
    ctx.store.comment(
        item.number,
        texts.watch_stop_comment.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
            step=step,
            reason=reason,
            failure=failure_lines(klass, left=left),
        ),
    )
    held = ctx.store.item(item.number) or item
    write_status(
        ctx.store,
        held,
        StatusFacts(stopped=True),
        marks={
            ImplementRecordKey.STOPPED: step,
            ImplementRecordKey.FAILURE: klass.value,
            ImplementRecordKey.LEFT_ACTION: left.value,
            ImplementRecordKey.CHECK: check,
            ImplementRecordKey.RESULT: ImplementResult.STOPPED.value,
        },
    )


def _stop_class(state: WatchState, check: str | None) -> FailureClass:
    """The class of the stop for `check`: `ci_infra` for a cancelled check, which is no failure of
    the code, else the class of its name, as the verdict reads it."""
    cancelled = any(
        item.name == check and item.bucket is CheckBucket.CANCEL
        for item in (state.checks.items if isinstance(state.checks, CheckVerdictSummary) else ())
    )
    if cancelled or check is None:
        return FailureClass.CI_INFRA
    return classify_failure(FailureEvidence(check=check))


def _ready_plan(
    ctx: _WatchContext,
    item: Item,
    pull: int,
    head: str,
    base_ref: str,
    checks: CheckVerdictSummary,
    labels: Sequence[str] = (),
) -> bool:
    """Mark the green plan draft `pull` ready, and record `stage.ready`; True when it marked it.
    A plan that needs a fix stays a draft. Then `draft_readiness` judges the draft that
    `read_ready_draft` reads (#6123): the record can hold one pull request as the plan and as the
    delivery of its item, and `read_draft` takes the kind from the record, so a delivery with a
    task that is not ticked stays a draft. The ledger keeps a refused head in `ready_head`, so the
    row judges that head once. Last, the Jev completeness check can hold the draft. A plan draft
    that is also the delivery of its item (`implement.pr`) takes the guards of the delivery ready
    path (`_delivery_held`): no stop, mode `on`, and no owner label on the pull request (`labels`)
    or the item (#6559)."""
    if item.job_record.get(StageRecordKey.NEEDS_FIX) == str(pull):
        return False
    if item.job_record.get(ImplementRecordKey.PR) == str(pull) and _delivery_held(item, labels):
        return False
    entry = ctx.recorded_pulls.get(pull)
    if entry is not None and entry.ready_head == head:
        return False
    draft = read_ready_draft(ctx.repo, pull, store=ctx.store, checks=checks)
    readiness = draft_readiness(draft)
    if readiness.answer is not Answer.READY:
        if entry is not None:
            entry.ready_head = head
        logger.info(
            "The watch row leaves %s#%d a draft: %s. %s",
            ctx.repo,
            pull,
            readiness.answer.value,
            readiness.reason,
        )
        return False
    if _jev_holds(ctx.store, ctx.repo, item, pull, head, base_ref):
        return False
    mark_ready(ctx.repo, pull, expected_head=head, draft=draft)
    ctx.store.set_marks(item, {StageRecordKey.READY: str(pull)})
    return True


def _delivery_held(item: Item, labels: Sequence[str]) -> bool:
    """Whether the delivery ready path leaves the delivery of `item` a draft (#6559): the item
    holds a stop, the mode of `roadmap.fix_checks.mode` is not `on`, or an owner label on the pull
    request (`labels`) or the item claims it, as the step `fix-checks` reads a claim."""
    return (
        bool(item.job_record.get(ImplementRecordKey.STOPPED))
        or load_settings().roadmap.fix_checks.mode != "on"
        or has_owner_label(labels)
        or has_owner_label(item.labels)
    )


def _ready_after_fix(ctx: _WatchContext, item: Item, pull: int, head: str) -> bool:
    """Run the ready path of the step `fix-checks` on a delivery draft that the path takes
    (`takes_ready_path`: a fix Job repaired it, or its implement Job ended at the draft) and whose
    checks pass, once for each head (#5027, #6559). The step marks the draft ready only when
    `draft_readiness` answers ready, and only in mode `on`; in mode `plan` it logs the plan. The
    step runs only the ready path: a check that fails after the read of the row gives `skipped`,
    with no repair and no comment (#6018)."""
    entry = ctx.recorded_pulls.get(pull)
    mode = load_settings().roadmap.fix_checks.mode
    if (
        mode == "off"
        or not takes_ready_path(item)
        or (entry is not None and entry.ready_head == head)
    ):
        return False
    report = run_fix_checks(
        ctx.store, ctx.repo, pull, head=head, confirm=mode == "on", ready_only=True
    )
    # The head counts as judged only once the path gave a report, so an error leaves it for the
    # next round (#6559).
    if entry is not None:
        entry.ready_head = head
    logger.info("The ready path of fix-checks on %s#%d: %s", ctx.repo, pull, report.to_json())
    return report.result is FixChecksResult.READY


def _apply_due_steps(
    ctx: _WatchContext,
    *,
    pr_number: int,
    item: Item,
    is_plan: bool,
    is_draft: bool,
    head_sha: str,
    base_ref: str,
    steps: Sequence[DueStep],
    entry: WatchLedgerEntry | None,
    checks: CheckVerdictSummary,
    labels: Sequence[str] = (),
) -> None:
    """Execute side-effects for active DueSteps. `labels` are the labels of the pull request."""
    client = get_github_session().client

    if DueStep.READY in steps:
        if is_plan:
            if _ready_plan(ctx, item, pr_number, head_sha, base_ref, checks, labels):
                ctx.marked_ready.append(pr_number)
        elif is_draft and _ready_after_fix(ctx, item, pr_number, head_sha):
            ctx.marked_ready.append(pr_number)

    if DueStep.COMMENT_CONFLICT in steps:
        if entry is None or entry.commented_head != head_sha:
            note = MESSAGES.roadmap.pr_conflicts_comment.format(
                number=pr_number, base=base_ref, head=head_sha[:_HEAD_CHARS]
            )
            # The marker alone is the key: the pull request holds one conflict comment, and a new
            # head edits it in place with that head (#6199).
            marker = "<!-- devops roadmap pr_conflicts -->"
            post(Target(ctx.repo, pr_number, client=client), marker, None, note)
            if pr_number in ctx.recorded_pulls:
                ctx.recorded_pulls[pr_number].commented_head = head_sha
            ctx.commented_conflicts.append(pr_number)

    if DueStep.STATUS_SYNC in steps:
        sync_status(ctx.store, item, facts_of(item, plan_merged=is_plan))
        ctx.recorded_pulls.pop(pr_number, None)


def _process_graphql_nodes(
    ctx: _WatchContext, nodes: list[dict[str, Any]], default_branch: str
) -> None:
    """Process pull request nodes retrieved via GraphQL."""
    for node in nodes:
        pr_number = int(node["number"])
        body = node.get("body") or ""
        base_ref = node.get("baseRefName") or default_branch
        is_draft = bool(node.get("isDraft"))
        head_sha = str(node.get("headRefOid") or "")
        author_login = (node.get("author") or {}).get("login", "")

        plan_item = _find_plan_item(ctx.store, pr_number, node.get("headRefName"))
        delivery_item = _delivers_an_item(ctx.store, body, base_ref, default_branch)

        if plan_item is not None:
            item = plan_item
            is_plan = True
        elif delivery_item is not None:
            item = delivery_item
            is_plan = False
        else:
            continue

        commit_nodes = (node.get("commits") or {}).get("nodes") or []
        commit_node = commit_nodes[0].get("commit") if commit_nodes else {}
        commit_message = commit_node.get("message") if commit_node else None
        rollup = commit_node.get("statusCheckRollup") if commit_node else None
        contexts = (rollup.get("contexts") or {}).get("nodes") if rollup else []

        if rollup is None or not contexts:
            checks: CheckVerdictSummary = CheckVerdictSummary(items=[no_checks_reported()])
        else:
            checks = CheckVerdictSummary(items=_parse_contexts(contexts))

        mergeable, mergeable_state = _parse_mergeable(node.get("mergeable"))
        label_nodes = (node.get("labels") or {}).get("nodes") or []
        labels = tuple(str(label.get("name") or "") for label in label_nodes)

        try:
            _evaluate_pull(
                ctx,
                pr_number=pr_number,
                item=item,
                is_plan=is_plan,
                head_sha=head_sha,
                base_ref=base_ref,
                is_draft=is_draft,
                mergeable=mergeable,
                mergeable_state=mergeable_state,
                author=author_login,
                checks=checks,
                commit_message=commit_message,
                labels=labels,
            )
        except GitHubNotAnIssueError as gone:
            gone.require_issue(item.number)
            continue


def _delivered_candidates(
    store: RoadmapStore,
    pull_numbers: tuple[int, ...],
    recorded_pulls: Mapping[int, WatchLedgerEntry],
) -> dict[int, tuple[Item | None, bool]]:
    """The candidates of a scoped round: the delivered pull requests that an open Item records as
    its plan (`recorded_plan`), or that the watch ledger holds. A delivered number that neither
    source names sends no request (#4413). The item of a candidate is a hint: the round reads the
    pull request, and takes the item only when the head branch is the recorded branch."""
    wanted = frozenset(pull_numbers)
    candidates: dict[int, tuple[Item | None, bool]] = {}
    for item in store.items():
        plan = recorded_plan(item)
        if (
            item.state is GitHubState.OPEN
            and plan is not None
            and plan.pull in wanted
            and item.job_record.get(StageRecordKey.READY) != str(plan.pull)
        ):
            candidates[plan.pull] = (item, True)
    for number in pull_numbers:
        if number not in candidates and number in recorded_pulls:
            candidates[number] = (None, False)
    return candidates


def _collect_rest_candidates(
    store: RoadmapStore,
    pull_numbers: tuple[int, ...] = (),
    recorded_pulls: Mapping[int, WatchLedgerEntry] | None = None,
) -> dict[int, tuple[Item | None, bool]]:
    """Gather candidate pull requests for REST processing. With `pull_numbers`, the candidates are
    the delivered pull requests only (#4413)."""
    if pull_numbers:
        return _delivered_candidates(store, pull_numbers, recorded_pulls or {})
    candidates: dict[int, tuple[Item | None, bool]] = {}
    for item in store.items():
        plan = recorded_plan(item)
        if plan is not None and item.job_record.get(StageRecordKey.READY) != str(plan.pull):
            candidates[plan.pull] = (item, True)
    for listed in store.open_pulls():
        if listed.number not in candidates:
            candidates[listed.number] = (None, False)
    return candidates


def _resolve_rest_item(
    store: RoadmapStore,
    pr_number: int,
    pull_status: PullStatus,
    known_item: Item | None,
    is_plan_hint: bool,
    default_branch: str,
) -> tuple[Item, bool] | None:
    """Resolve the Item and plan indicator for a REST pull request."""
    if known_item is not None:
        return known_item, is_plan_hint
    plan_item = _find_plan_item(store, pr_number, pull_status.head_ref)
    if plan_item is not None:
        return plan_item, True
    delivery_item = _delivers_an_item(store, pull_status.body, pull_status.base_ref, default_branch)
    if delivery_item is not None:
        return delivery_item, False
    return None


def _record_closed_plan_rest(
    ctx: _WatchContext,
    pr_number: int,
    pull_status: PullStatus,
    known_item: Item | None,
    is_plan_hint: bool,
) -> None:
    """Record a closed stage plan PR during REST fallback, leaving out an item that left (#7363)."""
    if known_item is not None and is_plan_hint:
        try:
            ctx.store.set_marks(known_item, {StageRecordKey.READY: str(pr_number)})
            if pull_status.merged:
                sync_status(ctx.store, known_item, facts_of(known_item, plan_merged=True))
        except GitHubNotAnIssueError as gone:
            gone.require_issue(known_item.number)
        ctx.recorded_pulls.pop(pr_number, None)


def _process_rest_pulls(
    ctx: _WatchContext, default_branch: str, pull_numbers: tuple[int, ...] = ()
) -> None:
    """Process roadmap pull requests via REST fallback. With `pull_numbers`, read the delivered
    pull requests of the scoped round only (#4413)."""
    client = get_github_session().client
    owner, name = ctx.repo.split("/", 1)
    candidate_prs = _collect_rest_candidates(ctx.store, pull_numbers, ctx.recorded_pulls)

    for pr_number, (known_item, is_plan_hint) in candidate_prs.items():
        pull_status: PullStatus = client.get_pull_status(ctx.repo, pr_number)
        # The record of the hinted item names the number. Only the head branch of the pull
        # request proves that it is the plan of that item (#7347).
        if known_item is not None and not _is_plan_of(known_item, pr_number, pull_status.head_ref):
            known_item, is_plan_hint = None, False
        if not pull_status.is_open_draft and not pull_status.draft and pull_status.state != "open":
            _record_closed_plan_rest(ctx, pr_number, pull_status, known_item, is_plan_hint)
            continue

        resolved = _resolve_rest_item(
            ctx.store, pr_number, pull_status, known_item, is_plan_hint, default_branch
        )
        if resolved is None:
            continue
        item, is_plan = resolved

        if _failed_head_in_backoff(ctx, pr_number, pull_status.head_sha, pull_status.base_ref):
            continue

        checks = read_check_runs(owner, name, pull_status.head_sha)
        pull_author = getattr(pull_status, "author", "") or ""

        try:
            _evaluate_pull(
                ctx,
                pr_number=pr_number,
                item=item,
                is_plan=is_plan,
                head_sha=pull_status.head_sha,
                base_ref=pull_status.base_ref,
                is_draft=pull_status.draft,
                mergeable=pull_status.mergeable,
                mergeable_state=pull_status.mergeable_state,
                author=pull_author,
                checks=checks,
                labels=pull_status.labels,
            )
        except GitHubNotAnIssueError as gone:
            gone.require_issue(item.number)
            continue


def _check_closed_stage_plans(ctx: _WatchContext, pull_numbers: tuple[int, ...] = ()) -> None:
    """Check recorded stage plan drafts that are no longer open. With `pull_numbers`, read the
    delivered plan pull requests of the scoped round only (#4413). A pull request whose head
    branch is not the recorded branch is not the plan of the item, and the row sends no write
    for it (#7347)."""
    client = get_github_session().client
    for item in ctx.store.items():
        plan = recorded_plan(item)
        if plan is None or item.job_record.get(StageRecordKey.READY) == str(plan.pull):
            continue
        plan_pr = plan.pull
        if pull_numbers and plan_pr not in pull_numbers:
            continue
        try:
            plan_status = client.get_pull_status(ctx.repo, plan_pr)
        except (GitHubOperationError, GitHubRateLimitError, GitHubNotFoundError, OSError) as exc:
            logger.warning("Could not read pull status for plan PR #%d: %s", plan_pr, exc)
            continue
        if not plan.is_pull(plan_pr, plan_status.head_ref):
            continue
        if not plan_status.is_open_draft:
            try:
                ctx.store.set_marks(item, {StageRecordKey.READY: str(plan_pr)})
                if plan_status.merged:
                    sync_status(ctx.store, item, facts_of(item, plan_merged=True))
            except GitHubNotAnIssueError as gone:
                gone.require_issue(item.number)
                continue
            ctx.recorded_pulls.pop(plan_pr, None)


def _process_poll(ctx: _WatchContext, owner: str, name: str, default_branch: str) -> None:
    """Process the open pull requests of the repository, the reconciling round of the row: one
    GraphQL read, or the REST fallback while the quota is on hold (ADR 0021, section 8; #5024)."""
    use_graphql = not _graphql_on_hold()
    graphql_nodes: list[dict[str, Any]] | None = None
    if use_graphql:
        try:
            graphql_nodes = _read_open_pulls_graphql(owner, name)
        except (
            GitHubOperationError,
            GitHubRateLimitError,
            RoadmapRunError,
            OSError,
            KeyError,
        ) as exc:
            logger.warning("GraphQL query failed for %s (%s); falling back to REST", ctx.repo, exc)
            use_graphql = False

    if use_graphql and graphql_nodes is not None:
        _process_graphql_nodes(ctx, graphql_nodes, default_branch)
    else:
        _process_rest_pulls(ctx, default_branch)
    _check_closed_stage_plans(ctx)


def watch_round(
    store: RoadmapStore,
    *,
    repo: str,
    ledger_path: Path,
    repo_dir: Path | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    pull_numbers: tuple[int, ...] = (),
) -> WatchRoundResult:
    """Run one tick of the watch row (ADR 0021, section 8; #5024).

    Reads open roadmap pull requests using GraphQL (or REST with ETag during hold),
    tracks state in watch.json with 30-minute failed head backoff, and routes
    steps via due_steps(state). With `pull_numbers`, a scoped round reads the delivered pull
    requests only, over REST, and sends no request for another pull request (#4413).
    """
    if dry_run:
        return WatchRoundResult()

    current_time = now or datetime.now(UTC)
    owner, name = repo.split("/", 1)
    default_branch = "main"

    ledger = WatchLedger.read(ledger_path)
    ctx = _WatchContext(
        store=store,
        repo=repo,
        current_time=current_time,
        recorded_pulls=dict(ledger.pulls),
        marked_ready=[],
        commented_conflicts=[],
        failed_heads=[],
    )

    try:
        if pull_numbers:
            _process_rest_pulls(ctx, default_branch, pull_numbers)
            _check_closed_stage_plans(ctx, pull_numbers)
        else:
            _process_poll(ctx, owner, name, default_branch)
    finally:
        WatchLedger(pulls=ctx.recorded_pulls).write(ledger_path)

    emit(ROADMAP_CONFLICTED_PULLS, ctx.total_conflicted, {"repo": repo})
    try:
        fixes = run_fix_checks_round(repo, ctx.fix_due, now=current_time, store=store)
    except (KubernetesError, ConfigurationError) as error:
        fixes = round_failed(repo, error)

    return WatchRoundResult(
        watched=ctx.watched_count,
        marked_ready=tuple(ctx.marked_ready),
        commented_conflicts=tuple(ctx.commented_conflicts),
        failed_heads=tuple(ctx.failed_heads),
        fix_checks=fixes,
    )
