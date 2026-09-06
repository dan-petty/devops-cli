"""Feedback dataset exporter for invalidated and verified AI review findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.review.pipeline import _get_reviews_base_dir
from devops_cli.config.constants import (
    CONST_STATUS_INVALIDATED,
)
from devops_cli.exceptions import SecurityError


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    persona: str
    title: str
    severity: str
    location: str
    description: str
    status: str = "INVALIDATED"
    verified: bool = False
    mitigated: bool = False
    confidence_score: float | None = None
    fix: str | None = None
    invalidation_reason: str | None = None
    verified_at: str | None = None
    verified_by: str | None = "human"


def _build_feedback_record(f: dict[str, Any], session_id: str, f_status: str) -> FeedbackRecord:
    """Construct FeedbackRecord from finding dictionary."""
    return FeedbackRecord(
        session_id=session_id,
        persona=str(f.get("persona") or "unknown"),
        title=str(f.get("title") or ""),
        severity=str(f.get("severity") or "medium"),
        location=str(f.get("location") or ""),
        description=str(f.get("description") or ""),
        status=f_status,
        verified=bool(f.get("verified", False)),
        mitigated=bool(f.get("mitigated", False)),
        confidence_score=f.get("confidence_score"),
        fix=f.get("fix"),
        invalidation_reason=f.get("invalidation_reason"),
        verified_at=f.get("verified_at"),
        verified_by=f.get("verified_by") or "human",
    )


def _extract_session_feedback_records(
    s_dir: Path, status_filter: str | None
) -> list[FeedbackRecord]:
    """Parse findings.json from a review session and extract matching FeedbackRecords."""
    try:
        data: dict[str, Any] = json.loads((s_dir / "findings.json").read_text(encoding="utf-8"))
    except Exception:
        return []

    records: list[FeedbackRecord] = []
    session_id = data.get("session_id", s_dir.name)
    filter_upper = status_filter.upper() if status_filter else None

    for f in data.get("findings", []):
        f_status = str(f.get("status", "")).upper()
        if filter_upper is not None and filter_upper != "ALL" and f_status != filter_upper:
            continue
        records.append(_build_feedback_record(f, session_id, f_status))

    return records


def export_invalidated_feedback(
    reviews_dir: Path | None = None,
    output_file: Path | None = None,
    status_filter: str | None = CONST_STATUS_INVALIDATED,
) -> tuple[int, Path]:
    """Export findings matching status_filter (or all findings if None) into a JSONL dataset.

    Returns (count, output_path).
    """
    if reviews_dir is not None:
        import tempfile

        resolved_r_dir = reviews_dir.resolve()
        workspace_root = Path.cwd().resolve()
        data_root = _get_reviews_base_dir().resolve().parent
        allowed_review_roots = [workspace_root, data_root, Path(tempfile.gettempdir()).resolve()]
        if not any(
            resolved_r_dir == root or resolved_r_dir.is_relative_to(root)
            for root in allowed_review_roots
        ):
            raise SecurityError(
                f"Reviews directory escapes allowed workspace, reviews data, or temporary directory: {reviews_dir}"
            )
        r_dir = resolved_r_dir
    else:
        r_dir = _get_reviews_base_dir()
    if output_file is not None:
        out_path = output_file
    else:
        from devops_cli.config.settings import load_settings
        from devops_cli.core.repo import find_top_level_repo_root

        settings = load_settings()
        out_path = settings.data.feedback_dataset_path
        if not out_path.is_absolute():
            out_path = (find_top_level_repo_root() / out_path).resolve()

    if output_file is not None:
        resolved_out = output_file.resolve()
        workspace_root = Path.cwd().resolve()
        data_root = _get_reviews_base_dir().resolve().parent
        allowed_roots = [workspace_root, data_root]
        if reviews_dir is not None:
            allowed_roots.append(reviews_dir.resolve().parent)
        import tempfile

        allowed_roots.append(Path(tempfile.gettempdir()).resolve())
        if not any(resolved_out.is_relative_to(root) for root in allowed_roots):
            raise SecurityError(f"Output path escapes allowed workspace directory: {output_file}")
        out_path = resolved_out

    if not r_dir.exists():
        return 0, out_path

    session_dirs = [d for d in r_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    records: list[FeedbackRecord] = []

    for s_dir in session_dirs:
        records.extend(_extract_session_feedback_records(s_dir, status_filter))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")

    return len(records), out_path
