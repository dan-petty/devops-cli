"""Feedback dataset exporter for invalidated AI review findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_FEEDBACK_DATASET_PATH,
    CONST_REVIEWS_DATA_DIR,
)


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    persona: str
    title: str
    severity: str
    location: str
    description: str
    invalidation_reason: str
    verified_at: str
    verified_by: str


def export_invalidated_feedback(
    reviews_dir: Path | None = None,
    output_file: Path | None = None,
) -> tuple[int, Path]:
    """Export all findings with status == "INVALIDATED" into a JSONL feedback dataset.

    Returns (count, output_path).
    """
    r_dir = reviews_dir or CONST_REVIEWS_DATA_DIR
    out_path = output_file or CONST_FEEDBACK_DATASET_PATH

    if not r_dir.exists():
        return 0, out_path

    session_dirs = [d for d in r_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    records: list[FeedbackRecord] = []

    for s_dir in session_dirs:
        try:
            data: dict[str, Any] = json.loads((s_dir / "findings.json").read_text(encoding="utf-8"))
            findings = data.get("findings", [])
            for f in findings:
                if f.get("status") == "INVALIDATED":
                    record = FeedbackRecord(
                        session_id=data.get("session_id", s_dir.name),
                        persona=f.get("persona", "unknown"),
                        title=f.get("title", ""),
                        severity=f.get("severity", "medium"),
                        location=f.get("location", ""),
                        description=f.get("description", ""),
                        invalidation_reason=f.get("invalidation_reason", ""),
                        verified_at=f.get("verified_at", ""),
                        verified_by=f.get("verified_by", "human"),
                    )
                    records.append(record)
        except Exception:
            continue

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")

    return len(records), out_path
