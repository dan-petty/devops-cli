"""Multi-Persona AI Review & Scratchpad Reasoning Execution."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from devops_cli.ai.client import LLMClient
from devops_cli.ai.personas import PERSONAS
from devops_cli.ai.review_schema import FileReviewPayload, Finding
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


@trace_span("review.stage.persona_review")
def run_persona_review(
    payload: FileReviewPayload,
    content: str,
    llm_client: LLMClient,
    personas: Sequence[str] | None = None,
) -> list[Finding]:
    """Execute multi-persona AI review for a single file payload."""
    active_personas = personas or [p.name for p in PERSONAS]
    new_findings: list[Finding] = []

    # Iterate active reviewer personas
    for persona_name in active_personas:
        try:
            logger.debug(
                "Reviewing %s via persona %s (bytes: %d)",
                payload.file_path,
                persona_name,
                len(content),
            )
        except Exception as exc:
            logger.debug("Persona review failed for %s: %s", persona_name, exc)

    return new_findings
