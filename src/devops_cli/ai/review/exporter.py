"""Feedback dataset exporter for the verdicts review findings were given.

The dataset is appended to, never replaced: an export adds each finding's verdict the dataset
does not already hold, read from findings.json and candidates.json, where the verdicts on the
findings a review kept out of its report live (#950). An export that finds nothing new leaves
the file as it was.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.review.review_environment import _get_reviews_base_dir
from devops_cli.config.constants import (
    CONST_REVIEW_CANDIDATES_FILENAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_STATUS_INVALIDATED,
    CONST_VERIFIED_BY_UNKNOWN,
)
from devops_cli.exceptions import SecurityError

logger = logging.getLogger(__name__)

_MAX_SESSION_FILE_BYTES = 50 * 1024 * 1024

# findings.json first: a finding it reports keeps the personas consolidation merged into it,
# and the copy candidates.json holds of it adds nothing.
_SESSION_FILES = (CONST_REVIEW_FINDINGS_FILENAME, CONST_REVIEW_CANDIDATES_FILENAME)


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    # What the session reviewed: its target and a digest of the pages its personas read.
    subject: dict[str, str] = Field(default_factory=dict)
    persona: str
    title: str
    severity: str
    location: str
    description: str
    category: str | None = None
    references: list[str] = Field(default_factory=list)
    # The lines the location cites, as the review read them; None for a session that predates
    # recording them (#950).
    cited_excerpt: str | None = None
    status: str = "INVALIDATED"
    verified: bool = False
    mitigated: bool = False
    confidence_score: float | None = None
    fix: str | None = None
    invalidation_reason: str | None = None
    verified_at: str | None = None
    # Only a finding that says a person judged it is `human`; anything else, `agent` included,
    # is not ground truth (#949).
    verified_by: str = CONST_VERIFIED_BY_UNKNOWN
    citation_line: int | None = None
    mitigating_mechanism: str | None = None


def feedback_fingerprint(record: dict[str, Any]) -> str:
    """What makes two dataset records one: the same session's finding with the same verdict.

    A finding is its session, first persona, location and title, and a finding judged again is
    a new record, so a person's later verdict is appended rather than dropped. Every record the
    dataset holds has these fields, so the records of earlier exports are fingerprinted too.
    """
    persona = str(record.get("persona") or "").split(",")[0].strip().lower()
    identity = [
        str(record.get("session_id") or ""),
        persona,
        str(record.get("location") or "").strip().lower(),
        str(record.get("title") or "").strip().lower(),
        str(record.get("status") or "").upper(),
        str(record.get("verified_by") or CONST_VERIFIED_BY_UNKNOWN),
    ]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def _build_feedback_record(
    f: dict[str, Any], session_id: str, subject: dict[str, str], f_status: str
) -> FeedbackRecord:
    """Construct FeedbackRecord from finding dictionary."""
    return FeedbackRecord(
        session_id=session_id,
        subject=subject,
        persona=str(f.get("persona") or "unknown"),
        title=str(f.get("title") or ""),
        severity=str(f.get("severity") or "medium"),
        location=str(f.get("location") or ""),
        description=str(f.get("description") or ""),
        category=f.get("category"),
        references=[str(r) for r in f.get("references") or []],
        cited_excerpt=(f.get("cited_code") or {}).get("excerpt"),
        status=f_status,
        verified=bool(f.get("verified", False)),
        mitigated=bool(f.get("mitigated", False)),
        confidence_score=f.get("confidence_score"),
        fix=f.get("fix"),
        invalidation_reason=f.get("invalidation_reason"),
        verified_at=f.get("verified_at"),
        # A missing adjudicator is unknown, not human. Defaulting to "human" put every
        # record the verifier never reached into the human ground-truth bucket -- the one
        # part of this dataset that is trusted precisely because a person wrote it.
        verified_by=f.get("verified_by") or CONST_VERIFIED_BY_UNKNOWN,
        citation_line=f.get("citation_line"),
        mitigating_mechanism=f.get("mitigating_mechanism"),
    )


def _read_session_file(path: Path) -> dict[str, Any]:
    """A session file's payload; empty when it is missing, oversized or unreadable."""
    try:
        if not path.is_file() or path.stat().st_size > _MAX_SESSION_FILE_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Corrupted or unreadable session file %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _extract_session_feedback_records(
    s_dir: Path, status_filter: str | None
) -> Iterator[FeedbackRecord]:
    """Yield the session's findings and candidates whose status the filter accepts."""
    filter_upper = status_filter.upper() if status_filter else None
    for file_name in _SESSION_FILES:
        data = _read_session_file(s_dir / file_name)
        session_id = str(data.get("session_id") or s_dir.name)
        subject = {str(k): str(v) for k, v in (data.get("subject") or {}).items()}
        for f in data.get("findings", []):
            f_status = str(f.get("status", "")).upper()
            if filter_upper is not None and filter_upper != "ALL" and f_status != filter_upper:
                continue
            yield _build_feedback_record(f, session_id, subject, f_status)


def _recorded_fingerprints(path: Path) -> set[str]:
    """The fingerprints of the records the dataset already holds."""
    if not path.is_file():
        return set()
    fingerprints: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            fingerprints.add(feedback_fingerprint(record))
    return fingerprints


def _resolve_reviews_dir(reviews_dir: Path | None) -> Path:
    """The reviews directory to read, refused when it escapes the allowed roots."""
    if reviews_dir is None:
        return _get_reviews_base_dir()
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
    return resolved_r_dir


def _resolve_output_path(output_file: Path | None, reviews_dir: Path | None) -> Path:
    """The dataset to append to: the configured one, or a given path the allowed roots hold."""
    if output_file is None:
        from devops_cli.config.settings import load_settings
        from devops_cli.core.repo import resolve_data_path

        return resolve_data_path(load_settings().data.feedback_dataset_path)
    import tempfile

    resolved_out = output_file.resolve()
    allowed_roots = [Path.cwd().resolve(), _get_reviews_base_dir().resolve().parent]
    if reviews_dir is not None:
        allowed_roots.append(reviews_dir.resolve().parent)
    allowed_roots.append(Path(tempfile.gettempdir()).resolve())
    if not any(
        resolved_out.is_relative_to(root) and resolved_out != root for root in allowed_roots
    ):
        raise SecurityError(f"Output path escapes allowed workspace directory: {output_file}")
    return resolved_out


def export_invalidated_feedback(
    reviews_dir: Path | None = None,
    output_file: Path | None = None,
    status_filter: str | None = CONST_STATUS_INVALIDATED,
) -> tuple[int, Path]:
    """Append the findings matching status_filter (all when None) the dataset does not hold yet.

    Returns (records appended, output_path). With nothing to append, the dataset is left as it
    was, and an absent one is not created.
    """
    r_dir = _resolve_reviews_dir(reviews_dir)
    out_path = _resolve_output_path(output_file, reviews_dir)
    if not r_dir.exists():
        return 0, out_path

    seen = _recorded_fingerprints(out_path)
    lines: list[str] = []
    for s_dir in sorted(d for d in r_dir.iterdir() if d.is_dir()):
        for rec in _extract_session_feedback_records(s_dir, status_filter):
            payload = rec.model_dump(mode="json")
            fingerprint = feedback_fingerprint(payload)
            if fingerprint not in seen:
                seen.add(fingerprint)
                lines.append(json.dumps(payload, ensure_ascii=False) + "\n")

    if lines:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as f:
            f.writelines(lines)
    return len(lines), out_path
