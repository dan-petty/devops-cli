"""Review pipeline stages used by the orchestrator: adversarial debate and report summaries."""

from __future__ import annotations

from devops_cli.ai.review.stages.adversarial_debate import run_adversarial_debate_stage
from devops_cli.ai.review.stages.reporting import synthesize_report_executive_summary

__all__ = [
    "run_adversarial_debate_stage",
    "synthesize_report_executive_summary",
]
