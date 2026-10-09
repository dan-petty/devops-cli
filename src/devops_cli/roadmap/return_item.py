"""`devops roadmap return`: return an unworkable item to New with evidence for refinement.

When an item cannot be built as specified, or requires an architectural refactor beyond its scope,
the agent writes no compensating code, comments on the issue with the evidence and proposed
re-scope/refactor, returns the item to New on the board, and stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from devops_cli.config.constants import CONST_ROADMAP_REFINE_BOARD_FILTER
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.roadmap.request_plan import StoreRequests
from devops_cli.roadmap.store import ItemField

if TYPE_CHECKING:
    from devops_cli.roadmap.store import RoadmapStore


@dataclass(frozen=True)
class ReturnPlan:
    """The plan to return an item to New with an evidence comment."""

    item_number: int
    title: str
    comment: str
    repo: str
    target_status: str = "New"


def plan_return(
    store: RoadmapStore,
    item_number: int,
    comment: str,
    repo: str,
) -> ReturnPlan:
    """Validate item exists on the board and return the ReturnPlan."""
    item = store.item(item_number)
    if item is None:
        raise DevOpsCLIError(f"Item #{item_number} is not on the roadmap board.")
    clean_comment = comment.strip()
    if not clean_comment:
        raise DevOpsCLIError("An evidence comment is required when returning an item to New.")
    return ReturnPlan(
        item_number=item_number,
        title=item.title,
        comment=clean_comment,
        repo=repo,
    )


def apply_return(store: RoadmapStore, plan: ReturnPlan) -> None:
    """Comment on the issue and move the board card to New."""
    item = store.item(plan.item_number)
    if item is None:
        raise DevOpsCLIError(f"Item #{plan.item_number} is not on the roadmap board.")
    store.comment(plan.item_number, plan.comment)
    store.set_field(item, ItemField.STATUS, plan.target_status)


def dry_run_return(
    repo: str,
    item_number: int,
) -> tuple[list[PlannedRequest], list[PlannedRequest]]:
    """Generate dry-run read and write requests for returning an item to New."""
    store_req = StoreRequests(repo, CONST_ROADMAP_REFINE_BOARD_FILTER)
    reads = [*store_req.card(f"item #{item_number}")]
    writes = [
        *store_req.comment(f"item #{item_number}"),
        *store_req.set_field(f"item #{item_number}", field_name="Status"),
    ]
    return reads, writes


def render_return_plan(plan: ReturnPlan) -> str:
    """Render the planned return summary for preview output."""
    lines = [
        f"Item #{plan.item_number}: {plan.title}",
        f"Target Status: {plan.target_status}",
        "Evidence Comment:",
        plan.comment,
    ]
    return "\n".join(lines)
