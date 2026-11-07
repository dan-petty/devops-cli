"""The writes of a finished alternatives plan, for the tests of the check (#4034)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.roadmap.alternatives import AlternativesPlan

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import RoadmapStore


def apply_alternatives(store: RoadmapStore, plan: AlternativesPlan) -> int:
    """Write the checks and the failures of a finished `plan` with the writer of the job, and
    return how many checks were written. A plan that `plan_alternatives` made without a writer is
    written the way a round writes it, so a test can look at the plan before it looks at the
    writes."""
    # Imported here, so that the fail-to-pass replay loads this module against a base tree that
    # has no `AlternativesWriter` yet.
    from devops_cli.roadmap.alternatives import AlternativesWriter

    writer = AlternativesWriter(store)
    for check in plan.checks:
        writer.settle(check)
    for failure in plan.failures:
        writer.settle(failure)
    return writer.written
