"""The roadmap step `fix-checks`: repair a failed check on a pull request (#5023).

Enforces safety bounds:
- Bot pull requests only.
- Stop on an owner/* label.
- Skip when the head commit moved.
- Soft cap of 3 rounds (extendable when error count decreases).
- Hard cap of 5 rounds.
- At most 3 distinct heads per pull request.

Two tiers of repair:
- Tier 1 (deterministic, 0 model calls): ruff check --fix and format, devops docs generate, uv lock.
- Tier 2 (model): run_fix_step within the plan scope.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from devops_cli.config.constants import CONST_ROADMAP_OWNER_SERVICE
from devops_cli.config.settings import load_settings
from devops_cli.git.branch_form import parse_branch
from devops_cli.github.check_verdict import CheckBucket, PRCheckItem, read_check_runs
from devops_cli.github.client import PullStatus
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.failure import FailureClass, FailureEvidence, classify_failure
from devops_cli.roadmap.implement.implement_fix_scope import repair_scope
from devops_cli.roadmap.implement.implement_pull import DraftKind, failed_log, kind_of
from devops_cli.roadmap.implement.implement_step import RoadmapImplementError, find_change
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.stores.store import FixChecksRecordKey, Item, RoadmapStore

logger = logging.getLogger(__name__)

_BOT_SUFFIX: Final[str] = "[bot]"


class FixChecksResult(StrEnum):
    """The result of the fix-checks step on a pull request (#5023)."""

    REPAIRED = "repaired"
    STOPPED = "stopped"
    SKIPPED = "skipped"
    WAIT = "wait"
    FAILED = "failed"


@dataclass(frozen=True)
class FixChecksReport:
    """The outcome of the fix-checks step for a pull request."""

    repo: str
    pull: int
    result: FixChecksResult
    head: str = ""
    rounds: int = 0
    errors: int = 0
    reason: str = ""

    def to_json(self) -> str:
        data: dict[str, Any] = {
            "job": "fix_checks",
            "repo": self.repo,
            "pull": self.pull,
            "result": self.result.value,
        }
        if self.head:
            data["head"] = self.head
        if self.rounds:
            data["rounds"] = self.rounds
        if self.errors:
            data["errors"] = self.errors
        if self.reason:
            data["reason"] = self.reason
        return json.dumps(data)


def count_errors(log: str) -> int:
    """Count the errors reported in a failed check log."""
    if not log or not log.strip():
        return 0
    if match := re.search(r"(\d+)\s+failed", log):
        return int(match.group(1))
    if match := re.search(r"Found\s+(\d+)\s+error", log, re.IGNORECASE):
        return int(match.group(1))
    if match := re.search(r"(\d+)\s+error", log, re.IGNORECASE):
        return int(match.group(1))
    lines_with_errors = sum(
        1 for line in log.splitlines() if re.search(r"\b(ERROR|FAILED|FAIL|error:)\b", line)
    )
    return lines_with_errors if lines_with_errors > 0 else 1


def dry_run_fix_checks(repo: str, pull: int) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Return empty request tuples for dry run (#5023)."""
    return (), ()


def _is_bot_author(author: str) -> bool:
    """Check if the pull request author is a bot."""
    if not author:
        return False
    if author.endswith(_BOT_SUFFIX) or author.endswith("-bot"):
        return True
    if author == CONST_ROADMAP_OWNER_SERVICE:
        return True
    bot = load_settings().service.github_app.bot_login
    return bool(bot and author == bot)


def _has_owner_label(labels: Sequence[Any]) -> bool:
    """Check if labels contain an owner/* label."""
    for label in labels:
        name = label.get("name") if isinstance(label, dict) else getattr(label, "name", str(label))
        if isinstance(name, str) and name.startswith("owner/"):
            return True
    return False


def _check_scope(worktree: Path, item_num: int, log: str, is_stage_plan: bool) -> bool:
    """Check whether the failed log names paths in the item repair scope."""
    try:
        if is_stage_plan:
            change = find_change(worktree, item_num, archived=False)
            folder = change.relative_to(worktree).as_posix()
            return bool(re.search(rf"(?<![\w.-]){re.escape(folder)}/", log))
        change = find_change(worktree, item_num, archived=True)
        tasks_file = change / "tasks.md"
        if not tasks_file.is_file():
            return False
        groups = parse_task_groups(tasks_file.read_text(encoding="utf-8"))
        scope = repair_scope(groups, change.relative_to(worktree).as_posix())
        return scope.names(log)
    except RoadmapImplementError, OSError, ValueError:
        return False


def _check_preconditions(
    status: PullStatus,
    head: str | None,
    item: Item | None,
    repo: str,
    pull: int,
    heads: Sequence[str],
) -> FixChecksReport | None:
    """Validate prerequisites before attempting any check repair."""
    if status.state != "open":
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=status.head_sha,
            reason="Pull request is closed or merged",
        )
    if head is not None and status.head_sha != head:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=status.head_sha,
            reason="Head has moved",
        )
    if not _is_bot_author(status.author):
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=status.head_sha,
            reason="Author is not a bot",
        )
    if _has_owner_label(status.labels) or (item is not None and _has_owner_label(item.labels)):
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=status.head_sha,
            reason="Item holds an owner label",
        )
    if len(heads) > 3:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=status.head_sha,
            reason="Exceeded maximum of 3 heads per pull request",
        )
    return None


def _check_caps(
    item: Item | None,
    current_rounds: int,
    errors: int,
    head_sha: str,
    repo: str,
    pull: int,
) -> FixChecksReport | None:
    """Check hard and soft caps on repair rounds."""
    if current_rounds >= 5:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=head_sha,
            rounds=current_rounds,
            errors=errors,
            reason="Hard cap reached (5 rounds)",
        )
    soft_cap = load_settings().roadmap.implement.repair_rounds
    prev_errors_str = item.job_record.get(FixChecksRecordKey.ERRORS) if item else None
    if current_rounds >= soft_cap and not (
        prev_errors_str is not None and errors < int(prev_errors_str)
    ):
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=head_sha,
            rounds=current_rounds,
            errors=errors,
            reason=f"Soft cap reached ({soft_cap} rounds) without error reduction",
        )
    return None


def _record_outcome(
    store: RoadmapStore,
    item: Item | None,
    head_sha: str,
    check_name: str,
    result: FixChecksResult,
    heads: Sequence[str],
    *,
    rounds: int | None = None,
    errors: int | None = None,
) -> None:
    """Record the step outcome in the item job record."""
    if item is None:
        return
    marks: dict[Any, str | None] = {
        FixChecksRecordKey.KEY: f"{head_sha}:{check_name}",
        FixChecksRecordKey.RESULT: result.value,
        FixChecksRecordKey.HEADS: ",".join(heads),
    }
    if rounds is not None:
        marks[FixChecksRecordKey.ROUNDS] = str(rounds)
    if errors is not None:
        marks[FixChecksRecordKey.ERRORS] = str(errors)
    store.set_marks(item, marks)


def _attempt_tier2(
    store: RoadmapStore,
    repo: str,
    pull: int,
    status: PullStatus,
    failed_check: PRCheckItem,
    log: str,
    item_num: int,
    item: Item | None,
    current_rounds: int,
    errors: int,
    heads: Sequence[str],
    source: Path | None,
    scope_checker: Callable[[str, int], bool] | None,
    model_fixer: Callable[..., Any] | None,
) -> FixChecksReport:
    """Run scope checking and tier 2 model repair."""
    is_plan = kind_of(item, pull) == DraftKind.STAGE_PLAN
    worktree = source or Path.cwd()
    scope_ok = (
        scope_checker(log, item_num)
        if scope_checker is not None
        else _check_scope(worktree, item_num, log, is_plan)
    )
    if not scope_ok:
        _record_outcome(
            store, item, status.head_sha, failed_check.name, FixChecksResult.STOPPED, heads
        )
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.STOPPED,
            head=status.head_sha,
            rounds=current_rounds,
            errors=errors,
            reason="Failed check log is outside plan scope",
        )

    if model_fixer is not None and model_fixer(store, repo, pull, failed_check.name, log, item_num):
        new_rounds = current_rounds + 1
        _record_outcome(
            store,
            item,
            status.head_sha,
            failed_check.name,
            FixChecksResult.REPAIRED,
            heads,
            rounds=new_rounds,
            errors=errors,
        )
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.REPAIRED,
            head=status.head_sha,
            rounds=new_rounds,
            errors=errors,
            reason="Tier 2 model repaired check",
        )

    _record_outcome(store, item, status.head_sha, failed_check.name, FixChecksResult.FAILED, heads)
    return FixChecksReport(
        repo=repo,
        pull=pull,
        result=FixChecksResult.FAILED,
        head=status.head_sha,
        rounds=current_rounds,
        errors=errors,
        reason="Model repair failed",
    )


def run_fix_checks(
    store: RoadmapStore,
    repo: str,
    pull: int,
    *,
    head: str | None = None,
    confirm: bool = False,
    session: Any = None,
    tier1_fixer: Callable[..., bool] | None = None,
    model_fixer: Callable[..., Any] | None = None,
    scope_checker: Callable[[str, int], bool] | None = None,
    source: Path | None = None,
) -> FixChecksReport:
    """Run one repair round for failed checks on pull request `pull` (#5023)."""
    gh_session = session or get_github_session()
    client = gh_session.client
    status: PullStatus = client.get_pull_status(repo, pull)

    parsed = parse_branch(status.head_ref)
    item_num = parsed.issue if parsed else pull
    item = store.item(item_num)

    heads_str = (item.job_record.get(FixChecksRecordKey.HEADS) or "") if item else ""
    heads = [h for h in heads_str.split(",") if h]
    if status.head_sha not in heads:
        heads.append(status.head_sha)

    if stopped := _check_preconditions(status, head, item, repo, pull, heads):
        return stopped

    owner, name = repo.split("/", 1)
    checks_summary = getattr(client, "checks", None) or read_check_runs(
        owner, name, status.head_sha
    )
    failed_checks = [c for c in checks_summary.items if c.bucket == CheckBucket.FAIL]
    if checks_summary.is_passing or not failed_checks:
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.SKIPPED,
            head=status.head_sha,
            reason="No failed check on head",
        )

    failed_check: PRCheckItem = failed_checks[0]
    log = getattr(client, "log", "") or failed_log(repo, failed_check)
    errors = count_errors(log)
    current_rounds = int((item.job_record.get(FixChecksRecordKey.ROUNDS) or 0) if item else 0)

    if cap_stopped := _check_caps(item, current_rounds, errors, status.head_sha, repo, pull):
        return cap_stopped

    if classify_failure(FailureEvidence(check=failed_check.name, log=log)) == FailureClass.CI_INFRA:
        comment = (
            f"CI infrastructure failure detected on check `{failed_check.name}`. "
            "Waiting for infrastructure resolution."
        )
        client.comment_on_pull(repo, pull, comment)
        _record_outcome(
            store, item, status.head_sha, failed_check.name, FixChecksResult.WAIT, heads
        )
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.WAIT,
            head=status.head_sha,
            rounds=current_rounds,
            errors=errors,
            reason="CI infrastructure failure; waiting",
        )

    if tier1_fixer is not None and tier1_fixer(repo, pull, failed_check.name, log):
        new_rounds = current_rounds + 1
        _record_outcome(
            store,
            item,
            status.head_sha,
            failed_check.name,
            FixChecksResult.REPAIRED,
            heads,
            rounds=new_rounds,
            errors=errors,
        )
        return FixChecksReport(
            repo=repo,
            pull=pull,
            result=FixChecksResult.REPAIRED,
            head=status.head_sha,
            rounds=new_rounds,
            errors=errors,
            reason="Tier 1 resolved check with 0 model requests",
        )

    return _attempt_tier2(
        store,
        repo,
        pull,
        status,
        failed_check,
        log,
        item_num,
        item,
        current_rounds,
        errors,
        heads,
        source,
        scope_checker,
        model_fixer,
    )
