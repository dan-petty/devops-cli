"""Modular review pipeline stages for multi-persona analysis, verification, and reporting."""

from __future__ import annotations

from devops_cli.ai.review.stages.adversarial_debate import run_adversarial_debate_stage
from devops_cli.ai.review.stages.persona_review import run_persona_review_stage
from devops_cli.ai.review.stages.pre_analysis import run_pre_analysis_stage
from devops_cli.ai.review.stages.reporting import run_reporting_stage
from devops_cli.ai.review.stages.reranking import run_reranking_stage
from devops_cli.ai.review.stages.static_scan import run_static_scan_stage
from devops_cli.ai.review.stages.verification import run_verification_stage

__all__ = [
    "run_adversarial_debate_stage",
    "run_persona_review_stage",
    "run_pre_analysis_stage",
    "run_reranking_stage",
    "run_reporting_stage",
    "run_static_scan_stage",
    "run_verification_stage",
]
