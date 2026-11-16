"""The status-lane row `watch`: one row watches open plan and delivery pull requests,
batches status queries via GraphQL with REST fallback during quota holds, maintains a
ledger with 30-minute failed-head backoff, and routes lifecycle steps (ADR 0021, section 8; #5024).

A live unit holds a pull request: a runner Job that no round reported (`job_holds`), or the
check-out of a stage Job. The record keeps the name of a runner Job that ended, so that name alone
holds nothing. After the ledger is written, the row runs the fix-checks units of the repository:
it starts a fix Job for each bot pull request that `due_steps` routes to `fix_checks`, and reports
the fix Jobs that ended (`fix_checks_row.py`, #5027). A Kubernetes or a configuration error stops
only that round: the row logs and counts it and gives its result (#6018). A delivery draft that a
fix Job repaired and whose checks pass gets the ready path of the step `fix-checks` once for each
head, and only the ready path: a check that fails between the two reads gives `skipped`. The row
leaves every other delivery draft to its implement Job.
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

from devops_cli.config.constants import CONST_ROADMAP_STAGE_COMMENT_MARKER
from devops_cli.config.defaults import (
    DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import (
    ConfigurationError,
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
    RoadmapRunError,
)
from devops_cli.exceptions.k8s import KubernetesError
from devops_cli.github.check_verdict import (
    CheckVerdictSummary,
    PRCheckItem,
    _resolve_bucket,
    no_checks_reported,
    read_check_runs,
)
from devops_cli.github.client import PullStatus
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.fix_checks_row import (
    FixChecksRound,
    FixDue,
    round_failed,
    run_fix_checks_round,
)
from devops_cli.roadmap.jev_completeness import (
    CompletenessOutcome,
    check_completeness,
    completeness_note,
)
from devops_cli.roadmap.release_feed import closing_numbers
from devops_cli.roadmap.stage.stage_criteria import acceptance_criteria
from devops_cli.roadmap.status_sync import facts_of, job_holds, sync_status
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.steps.fix_checks import FixChecksResult, run_fix_checks
from devops_cli.roadmap.steps.ready import mark_ready
from devops_cli.roadmap.steps.watch import (
    DueStep,
    PRVerdict,
    WatchState,
    due_steps,
    fix_checks_check,
    verdict,
)
from devops_cli.roadmap.stores.store import (
    FixChecksRecordKey,
    GitHubState,
    Item,
    RoadmapStore,
    StageRecordKey,
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
        baseRefName
        author {
          login
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


def _parse_contexts(contexts_nodes: Sequence[Mapping[str, Any]]) -> list[PRCheckItem]:
    """Parse GraphQL CheckRun and StatusContext nodes into PRCheckItems."""
    items: list[PRCheckItem] = []
    for node in contexts_nodes:
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


def _find_plan_item(store: RoadmapStore, pull_number: int) -> Item | None:
    """Find open item whose stage.pr matches pull_number."""
    for item in store.items():
        if item.state is GitHubState.OPEN:
            recorded = item.job_record.get(StageRecordKey.PR) or ""
            if recorded.isdigit() and int(recorded) == pull_number:
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
) -> None:
    """Evaluate one roadmap pull request and apply lifecycle steps."""
    ctx.watched_count += 1
    has_live_unit = job_holds(item) or bool(item.job_record.get(StageRecordKey.JOB))

    entry = ctx.recorded_pulls.get(pr_number)
    if entry is not None and entry.verdict == PRVerdict.FAILED.value:
        if entry.head == head_sha and entry.base == base_ref:
            if entry.next_read_at:
                next_time = datetime.fromisoformat(entry.next_read_at)
                if ctx.current_time < next_time:
                    ctx.failed_heads.append(pr_number)
                    return

    if mergeable is False and not is_draft and not is_plan:
        ctx.total_conflicted += 1

    is_bot = is_plan or (author.endswith("[bot]") if author else False)

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
    )

    v = verdict(state)
    steps = due_steps(state)
    if DueStep.FIX_CHECKS in steps and (check := fix_checks_check(state)) is not None:
        units = item.job_record.get(FixChecksRecordKey.UNITS)
        ctx.fix_due.append(FixDue(pr_number, head_sha, check, item.number, units))

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
    )


def _ready_after_fix(ctx: _WatchContext, item: Item, pull: int, head: str) -> bool:
    """Run the ready path of the step `fix-checks` on a delivery draft that a fix Job repaired and
    whose checks pass, once for each head (#5027). The step marks the draft ready only when
    `draft_readiness` answers ready, and only in mode `on`; in mode `plan` it logs the plan. The
    step runs only the ready path: a check that fails after the read of the row gives `skipped`,
    with no repair and no comment (#6018). A delivery draft that no fix Job repaired is the
    implement Job's: the row leaves it."""
    entry = ctx.recorded_pulls.get(pull)
    mode = load_settings().roadmap.fix_checks.mode
    repaired = item.job_record.get(FixChecksRecordKey.RESULT) == FixChecksResult.REPAIRED
    if mode == "off" or not repaired or (entry is not None and entry.ready_head == head):
        return False
    if entry is not None:
        entry.ready_head = head
    report = run_fix_checks(
        ctx.store, ctx.repo, pull, head=head, confirm=mode == "on", ready_only=True
    )
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
) -> None:
    """Execute side-effects for active DueSteps."""
    client = get_github_session().client

    if DueStep.READY in steps:
        if is_plan:
            if item.job_record.get(StageRecordKey.NEEDS_FIX) == str(pr_number):
                pass
            elif _jev_holds(ctx.store, ctx.repo, item, pr_number, head_sha, base_ref):
                pass
            else:
                mark_ready(ctx.repo, pr_number, expected_head=head_sha)
                ctx.store.set_marks(item, {StageRecordKey.READY: str(pr_number)})
                ctx.marked_ready.append(pr_number)
        elif is_draft and _ready_after_fix(ctx, item, pr_number, head_sha):
            ctx.marked_ready.append(pr_number)

    if DueStep.COMMENT_CONFLICT in steps:
        if entry is None or entry.commented_head != head_sha:
            note = MESSAGES.roadmap.pr_conflicts_comment.format(
                number=pr_number, base=base_ref, head=head_sha[:_HEAD_CHARS]
            )
            marker = "<!-- devops roadmap pr_conflicts -->"
            post(
                Target(ctx.repo, pr_number, client=client),
                marker,
                head_sha[:_HEAD_CHARS],
                note,
            )
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

        plan_item = _find_plan_item(ctx.store, pr_number)
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
        )


def _collect_rest_candidates(store: RoadmapStore) -> dict[int, tuple[Item | None, bool]]:
    """Gather candidate pull requests for REST processing."""
    candidates: dict[int, tuple[Item | None, bool]] = {}
    for item in store.items():
        rec = item.job_record.get(StageRecordKey.PR)
        if rec and rec.isdigit() and item.job_record.get(StageRecordKey.READY) != rec:
            candidates[int(rec)] = (item, True)
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
    plan_item = _find_plan_item(store, pr_number)
    if plan_item is not None:
        return plan_item, True
    delivery_item = _delivers_an_item(store, pull_status.body, pull_status.base_ref, default_branch)
    if delivery_item is not None:
        return delivery_item, False
    return None


def _process_rest_pulls(ctx: _WatchContext, default_branch: str) -> None:
    """Process roadmap pull requests via REST fallback."""
    client = get_github_session().client
    owner, name = ctx.repo.split("/", 1)
    candidate_prs = _collect_rest_candidates(ctx.store)

    for pr_number, (known_item, is_plan_hint) in candidate_prs.items():
        pull_status: PullStatus = client.get_pull_status(ctx.repo, pr_number)
        if not pull_status.is_open_draft and not pull_status.draft and pull_status.state != "open":
            if known_item is not None and is_plan_hint:
                ctx.store.set_marks(known_item, {StageRecordKey.READY: str(pr_number)})
                if pull_status.merged:
                    sync_status(ctx.store, known_item, facts_of(known_item, plan_merged=True))
                ctx.recorded_pulls.pop(pr_number, None)
            continue

        resolved = _resolve_rest_item(
            ctx.store, pr_number, pull_status, known_item, is_plan_hint, default_branch
        )
        if resolved is None:
            continue
        item, is_plan = resolved

        checks = read_check_runs(owner, name, pull_status.head_sha)
        pull_author = getattr(pull_status, "author", "") or ""

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
        )


def _check_closed_stage_plans(ctx: _WatchContext) -> None:
    """Check recorded stage plan drafts that are no longer open."""
    client = get_github_session().client
    for item in ctx.store.items():
        recorded = item.job_record.get(StageRecordKey.PR)
        if not recorded or not recorded.isdigit():
            continue
        if item.job_record.get(StageRecordKey.READY) == recorded:
            continue
        plan_pr = int(recorded)
        try:
            plan_status = client.get_pull_status(ctx.repo, plan_pr)
        except (GitHubOperationError, GitHubRateLimitError, GitHubNotFoundError, OSError) as exc:
            logger.warning("Could not read pull status for plan PR #%d: %s", plan_pr, exc)
            continue
        if not plan_status.is_open_draft:
            ctx.store.set_marks(item, {StageRecordKey.READY: str(plan_pr)})
            if plan_status.merged:
                sync_status(ctx.store, item, facts_of(item, plan_merged=True))
            ctx.recorded_pulls.pop(plan_pr, None)


def watch_round(
    store: RoadmapStore,
    *,
    repo: str,
    ledger_path: Path,
    repo_dir: Path | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> WatchRoundResult:
    """Run one tick of the watch row (ADR 0021, section 8; #5024).

    Reads open roadmap pull requests using GraphQL (or REST with ETag during hold),
    tracks state in watch.json with 30-minute failed head backoff, and routes
    steps via due_steps(state).
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
            logger.warning("GraphQL query failed for %s (%s); falling back to REST", repo, exc)
            use_graphql = False

    try:
        if use_graphql and graphql_nodes is not None:
            _process_graphql_nodes(ctx, graphql_nodes, default_branch)
        else:
            _process_rest_pulls(ctx, default_branch)

        _check_closed_stage_plans(ctx)
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
