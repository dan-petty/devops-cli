"""Feedback dataset exporter for invalidated AI review findings (backwards compatibility alias)."""

from __future__ import annotations

from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback

__all__ = ["FeedbackRecord", "export_invalidated_feedback"]
