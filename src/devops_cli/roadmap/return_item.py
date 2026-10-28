"""`devops roadmap return`: return an unworkable item to New with evidence for refinement.

When an item cannot be built as specified, or requires an architectural refactor beyond its scope,
the agent writes no compensating code, comments on the issue with the evidence and proposed
re-scope/refactor, sets its Status to New (the `status/new` label), and stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from devops_cli.config.constants import CONST_ROADMAP_STATUS_NEW
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
    target_status: str = CONST_ROADMAP_STATUS_NEW


def plan_return(
    store: RoadmapStore,
    item_number: int,
    comment: str,
    repo: str,
) -> ReturnPlan:
    """Validate that the issue is an item of the roadmap and return the ReturnPlan."""
    item = store.item(item_number)
    if item is None:
        raise DevOpsCLIError(f"#{item_number} is not an item of the roadmap.")
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
    """Comment on the issue and set its Status to New."""
    item = store.item(plan.item_number)
    if item is None:
        raise DevOpsCLIError(f"#{plan.item_number} is not an item of the roadmap.")
    store.comment(plan.item_number, plan.comment)
    store.set_field(item, ItemField.STATUS, plan.target_status)


def dry_run_return(
    repo: str,
    item_number: int,
) -> tuple[list[PlannedRequest], list[PlannedRequest]]:
    """Generate dry-run read and write requests for returning an item to New."""
    store_req = StoreRequests(repo)
    subject = f"#{item_number}"
    reads = [*store_req.issue(subject)]
    writes = [
        *store_req.issue(subject),
        *store_req.comment(subject),
        *store_req.set_field(subject, field_name=ItemField.STATUS.value),
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
