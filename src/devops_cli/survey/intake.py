"""Roadmap intake integration for outward-facing capability gap candidates."""

from __future__ import annotations

import logging

from devops_cli.lang import MESSAGES
from devops_cli.output import print_info, print_success
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.intake import CandidateOutcome, Filer, NewCandidate, intake_candidate
from devops_cli.roadmap.intake_model import IntakeModel, build_intake_model
from devops_cli.roadmap.store import RoadmapStore
from devops_cli.survey.models import CapabilityGap

logger = logging.getLogger(__name__)


def emit_gap_to_intake(
    gap: CapabilityGap,
    store: RoadmapStore,
    *,
    repo: str,
    model: IntakeModel,
    confirm: bool = False,
) -> CandidateOutcome:
    """Emit one capability gap candidate to roadmap intake."""
    title = f"feat(cli): {gap.capability}"
    body = (
        "## Context & Rationale\n"
        f"Outward-facing capability survey identified a capability gap.\n"
        f"The feature is present in comparable tool '{gap.tool}' but absent in devops-cli.\n\n"
        "## Scope & Deliverables\n"
        f"{gap.description or gap.capability}\n\n"
        "## Source Citation\n"
        f"{gap.citation}\n"
    )
    candidate = NewCandidate(
        title=title,
        body=body,
        source=gap.citation,
        filed_by=Filer.AGENT,
    )
    outcome = intake_candidate(
        store=store,
        candidate=candidate,
        repo=repo,
        model=model,
        confirm=confirm,
    )
    return outcome


def emit_all_gaps_to_intake(
    gaps: list[CapabilityGap],
    *,
    repo: str,
    store: RoadmapStore | None = None,
    model: IntakeModel | None = None,
    confirm: bool = False,
) -> list[CandidateOutcome]:
    """Emit all discovered capability gaps to roadmap intake."""
    if not gaps:
        print_info(MESSAGES.survey.no_gaps_found)
        return []

    target_store = store
    if target_store is None:
        target_store = roadmap_store.get_roadmap_store(repo)

    target_model = model if model is not None else build_intake_model()
    outcomes: list[CandidateOutcome] = []

    for gap in gaps:
        outcome = emit_gap_to_intake(
            gap,
            target_store,
            repo=repo,
            model=target_model,
            confirm=confirm,
        )
        outcomes.append(outcome)
        if outcome.number is not None:
            print_success(
                MESSAGES.survey.candidate_filed.format(
                    number=outcome.number,
                    capability=gap.capability,
                )
            )
        else:
            print_info(
                MESSAGES.survey.candidate_emitted.format(
                    capability=gap.capability,
                    tool=gap.tool,
                )
            )

    return outcomes
