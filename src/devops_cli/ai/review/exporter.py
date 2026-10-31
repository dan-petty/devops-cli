"""Feedback dataset exporter for the verdicts review findings were given.

The dataset is appended to, never replaced: an export adds each finding's verdict the dataset
does not already hold, read from findings.json and candidates.json, where the verdicts on the
findings a review kept out of its report live (#950). An export that finds nothing new leaves
the file as it was.

A subject reviewed more than once is exported once (#877). The sessions of one subject
(`history.subject_key`) share their findings by fingerprint v2, and each finding is exported
with one verdict: a person's, the one with the newest `verified_at`, when any session of the
subject holds one; otherwise the one of the session that review history counts for the subject
(#607). A session that records no subject is a subject of its own, and a finding without a
fingerprint v2 is matched only within its own session: no title or location match.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from devops_cli.ai.review.history import load_review_history, subject_key
from devops_cli.config.constants import (
    CONST_REVIEW_CANDIDATES_FILENAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_STATUS_INVALIDATED,
    CONST_VERIFIED_BY_HUMAN,
    CONST_VERIFIED_BY_UNKNOWN,
)
from devops_cli.exceptions import SecurityError
from devops_cli.review.session import ReviewSessionStore

logger = logging.getLogger(__name__)

_MAX_SESSION_FILE_BYTES = 50 * 1024 * 1024

# findings.json first: a finding it reports keeps the personas consolidation merged into it,
# and the copy candidates.json holds of it adds nothing.
_SESSION_FILES = (CONST_REVIEW_FINDINGS_FILENAME, CONST_REVIEW_CANDIDATES_FILENAME)

# A session's rank among its subject's sessions (`ReviewSessionRecord.rank`), and the order of
# the copies of one finding (`_precedence`).
type _Rank = tuple[int, int, datetime, str]
type _Order = tuple[bool, datetime, _Rank]

# Ranks a verdict without a readable time, and a session review history does not hold, lowest.
_EARLIEST = datetime.min.replace(tzinfo=UTC)
_UNRANKED: _Rank = (-1, -1, _EARLIEST, "")


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    # What the session reviewed: its target and a digest of the pages its personas read.
    subject: dict[str, str] = Field(default_factory=dict)
    # Equal for the sessions of one subject; None for a session that records no subject (#877).
    subject_key: str | None = None
    # The admitted finding's fingerprint v2 (#1141); None for a finding admission did not build.
    fingerprint_v2: str | None = None
    producer: str = Field(default="", validation_alias=AliasChoices("producer", "persona"))

    @property
    def persona(self) -> str:
        return self.producer

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


def _finding_identity(record: dict[str, Any]) -> list[str]:
    """What makes two copies of a finding one finding.

    A finding with a fingerprint v2 is its subject's finding of that fingerprint, or its session's
    when the session records no subject. A finding without one is its session, producer, location
    and title.
    """
    fingerprint = record.get("fingerprint_v2")
    if fingerprint:
        owner = record.get("subject_key") or record.get("session_id") or ""
        return [str(owner), str(fingerprint)]
    producer = (
        str(record.get("producer") or record.get("persona") or "").split(",")[0].strip().lower()
    )
    return [
        str(record.get("session_id") or ""),
        producer,
        str(record.get("location") or "").strip().lower(),
        str(record.get("title") or "").strip().lower(),
    ]


def feedback_fingerprint(record: dict[str, Any]) -> str:
    """What makes two dataset records one: the same finding with the same verdict.

    A finding judged again is a new record, so a person's later verdict is appended rather than
    dropped. A record of an earlier export that holds no fingerprint v2 is identified by its
    session, producer, location and title, as every finding without one is.
    """
    identity = [
        *_finding_identity(record),
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
        subject_key=subject_key(subject),
        fingerprint_v2=str(f.get("fingerprint") or "") or None,
        producer=str(f.get("producer") or f.get("persona") or "unknown"),
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


def _extract_session_feedback_records(s_dir: Path) -> Iterator[FeedbackRecord]:
    """Yield the session's findings, then its candidates, each with its verdict."""
    for file_name in _SESSION_FILES:
        data = _read_session_file(s_dir / file_name)
        session_id = str(data.get("session_id") or s_dir.name)
        subject = {str(k): str(v) for k, v in (data.get("subject") or {}).items()}
        for f in data.get("findings", []):
            yield _build_feedback_record(f, session_id, subject, str(f.get("status", "")).upper())


def _verdict_time(record: FeedbackRecord) -> datetime:
    """When the record's verdict was given; the earliest time when it records none it can read."""
    try:
        given = datetime.fromisoformat(record.verified_at or "")
    except ValueError:
        return _EARLIEST
    return given if given.tzinfo is not None else given.replace(tzinfo=UTC)


def _precedence(record: FeedbackRecord, session_rank: _Rank) -> _Order:
    """Orders the copies of one finding; the highest is the one exported.

    A person's verdict comes first, the newest first. Then the copy of the session that review
    history ranks highest among its subject's sessions, which is the session it counts.
    """
    human = record.verified_by == CONST_VERIFIED_BY_HUMAN
    return human, _verdict_time(record) if human else _EARLIEST, session_rank


def _subject_findings(r_dir: Path) -> list[FeedbackRecord]:
    """One copy of each finding of each subject under `r_dir`, in the order they were read."""
    ranks = {s.path.name: s.rank for s in load_review_history(r_dir).sessions}
    chosen: dict[str, tuple[_Order, FeedbackRecord]] = {}
    for s_dir in sorted(d for d in r_dir.iterdir() if d.is_dir()):
        session_rank = ranks.get(s_dir.name, _UNRANKED)
        for rec in _extract_session_feedback_records(s_dir):
            key = json.dumps(_finding_identity(rec.model_dump(mode="json")))
            order = _precedence(rec, session_rank)
            if key not in chosen or order > chosen[key][0]:
                chosen[key] = (order, rec)
    return [rec for _, rec in chosen.values()]


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


def _resolve_reviews_dir(reviews_dir: Path | None, workspace_root: Path) -> Path:
    """The reviews directory to read, refused when it escapes the allowed roots."""
    if reviews_dir is None:
        return ReviewSessionStore.root()
    import tempfile

    resolved_r_dir = reviews_dir.resolve()
    data_root = ReviewSessionStore.root().parent
    allowed_review_roots = [workspace_root, data_root, Path(tempfile.gettempdir()).resolve()]
    if not any(
        resolved_r_dir == root or resolved_r_dir.is_relative_to(root)
        for root in allowed_review_roots
    ):
        raise SecurityError(
            f"Reviews directory escapes allowed workspace, reviews data, or temporary directory: {reviews_dir}"
        )
    return resolved_r_dir


def _resolve_output_path(
    output_file: Path | None, reviews_dir: Path | None, workspace_root: Path
) -> Path:
    """The dataset to append to: the configured one, or a given path the allowed roots hold."""
    if output_file is None:
        from devops_cli.config.settings import load_settings
        from devops_cli.core.repo import resolve_review_data_path

        return resolve_review_data_path(load_settings().data.feedback_dataset_path)
    import tempfile

    resolved_out = output_file.resolve()
    allowed_roots = [workspace_root, ReviewSessionStore.root().parent]
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
    *,
    workspace_root: Path,
    dry_run: bool = False,
) -> tuple[int, Path]:
    """Append the findings matching status_filter (all when None) the dataset does not hold yet.

    Each finding of a subject is exported once, with the verdict the module docstring names; the
    filter reads that verdict, so a verdict a person overturned is not exported.

    Returns (records appended, output_path). With nothing to append, the dataset is left as it
    was, and an absent one is not created.

    A given reviews directory or output path must lie under `workspace_root`, the data root or the
    temporary directory. The command gives the directory that it runs in as `workspace_root`: the
    working directory of the process is no root of its own (#2098).
    """
    root = workspace_root.resolve()
    r_dir = _resolve_reviews_dir(reviews_dir, root)
    out_path = _resolve_output_path(output_file, reviews_dir, root)
    if not r_dir.exists():
        return 0, out_path

    filter_upper = status_filter.upper() if status_filter else "ALL"
    seen = _recorded_fingerprints(out_path)
    lines: list[str] = []
    for rec in _subject_findings(r_dir):
        if filter_upper != "ALL" and rec.status != filter_upper:
            continue
        payload = rec.model_dump(mode="json")
        fingerprint = feedback_fingerprint(payload)
        if fingerprint not in seen:
            seen.add(fingerprint)
            lines.append(json.dumps(payload, ensure_ascii=False) + "\n")

    if lines and not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as f:
            f.writelines(lines)
    return len(lines), out_path
