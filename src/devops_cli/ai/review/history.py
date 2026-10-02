"""Review history: the completed sessions in a reviews directory, one counted per subject (#607).

Every session records its subject: the target type and ref it reviewed, and a digest of the
review pages. A re-review, or each run of `devops review benchmark`, is a repeat of one subject,
and the figures that compare sessions count one session per subject. That session is the one
with the most human verdicts, then the most findings with any verdict, then the newest. A machine
re-run, or a run whose verification was skipped, never displaces verdicts a person wrote.

The session being compared is left out before repeats collapse, so it is never part of its own
history, and earlier sessions of its subject still count once. Sessions written before subjects
existed each count on their own: target-only when they have a profile.json, unkeyed otherwise. A
key never comes from a directory name.

The reader parses only the fields the figures read. A full `ReviewSessionPayload` parse normalizes
every finding's verification criteria, which took seconds over one workstation's history.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from devops_cli.ai.review.profile import ReviewProfile
from devops_cli.ai.review_schema import normalize_finding_status
from devops_cli.ai.run_store import digest
from devops_cli.config.constants import (
    CONST_REVIEW_CANDIDATES_FILENAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_STATUS_UNVERIFIED,
    CONST_VERIFIED_BY_HUMAN,
)
from devops_cli.config.defaults import DEFAULT_FINDING_STATUS

logger = logging.getLogger(__name__)

# Ranks a session whose findings.json has no readable time below every dated one.
_UNDATED = datetime.min.replace(tzinfo=UTC)


def review_subject(target_type: str, target_ref: str, pages: Sequence[str]) -> dict[str, str]:
    """What a review session reviewed: its target, and a digest of the pages its personas read.

    The pages are the diff or file contents after paging and redaction, so one rule covers PRs,
    branches, working-tree diffs and paths, with no git or GitHub call.
    """
    pages_digest = hashlib.sha256("\n".join(pages).encode()).hexdigest()[:16]
    return {"type": target_type, "ref": target_ref, "input": pages_digest}


def subject_key(subject: dict[str, str]) -> str | None:
    """Equal for sessions of one subject; None for a session that records no subject.

    `digest({})` is a single value, which would collapse every older session into one.
    """
    return digest(subject) if subject else None


class HistoryFinding(BaseModel):
    """The fields of a saved finding that history's figures read."""

    title: str = ""
    description: str = ""
    category: str | None = None
    invalidation_reason: str | None = None
    status: str = DEFAULT_FINDING_STATUS
    verified_by: str | None = None
    persona: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: object) -> str:
        return normalize_finding_status(v)


class _HistoryPayload(BaseModel):
    """The fields of findings.json and candidates.json that history reads."""

    generated_at: str = ""
    subject: dict[str, str] = Field(default_factory=dict)
    findings: list[HistoryFinding] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReviewSessionRecord:
    """One completed review session, as history reads it."""

    path: Path
    subject_key: str | None
    # The profile.json target of a session that has one.
    target: str | None
    generated_at: datetime | None
    # findings.json: the reported findings, and the only file human verdicts are written to.
    findings: tuple[HistoryFinding, ...]
    # Every finding the session raised: candidates.json, or findings.json without one.
    raised: tuple[HistoryFinding, ...]

    @property
    def rank(self) -> tuple[int, int, datetime, str]:
        """Orders the sessions of one subject; the highest is the one history counts."""
        human = sum(1 for f in self.findings if f.verified_by == CONST_VERIFIED_BY_HUMAN)
        judged = sum(1 for f in self.raised if f.status != CONST_STATUS_UNVERIFIED)
        return human, judged, self.generated_at or _UNDATED, self.path.name


@dataclass(frozen=True, slots=True)
class ReviewHistory:
    """The completed sessions in a reviews directory, and the ones its figures count."""

    sessions: tuple[ReviewSessionRecord, ...]
    counted: tuple[ReviewSessionRecord, ...]

    @property
    def repeats(self) -> int:
        """Sessions left out because another session of their subject counts."""
        return len(self.sessions) - len(self.counted)

    @property
    def target_only(self) -> int:
        """Sessions without a subject that have a profile target."""
        return sum(1 for s in self.sessions if s.subject_key is None and s.target is not None)

    @property
    def unkeyed(self) -> int:
        """Sessions with neither a subject nor a profile target."""
        return sum(1 for s in self.sessions if s.subject_key is None and s.target is None)


def load_review_history(reviews_dir: Path, exclude: Path | None = None) -> ReviewHistory:
    """Read the completed sessions under `reviews_dir` and pick the ones the figures count.

    `exclude`, the session being compared, is dropped before repeats collapse.
    """
    if not reviews_dir.is_dir():
        return ReviewHistory(sessions=(), counted=())
    excluded = exclude.resolve() if exclude is not None else None
    sessions = tuple(
        _read_session(session_dir)
        for session_dir in sorted(reviews_dir.iterdir())
        if (session_dir / CONST_REVIEW_FINDINGS_FILENAME).is_file()
        and session_dir.resolve() != excluded
    )
    return ReviewHistory(sessions=sessions, counted=_count_once_per_subject(sessions))


def _count_once_per_subject(
    sessions: tuple[ReviewSessionRecord, ...],
) -> tuple[ReviewSessionRecord, ...]:
    """Keep the highest-ranked session of each subject, and every session without one."""
    best: dict[str, ReviewSessionRecord] = {}
    for session in sessions:
        if session.subject_key is None:
            continue
        current = best.get(session.subject_key)
        if current is None or session.rank > current.rank:
            best[session.subject_key] = session
    return tuple(s for s in sessions if s.subject_key is None or best[s.subject_key] is s)


def _read_session(session_dir: Path) -> ReviewSessionRecord:
    """Read a session; an unreadable findings.json leaves it with no findings and no subject."""
    reported = _read_payload(session_dir / CONST_REVIEW_FINDINGS_FILENAME) or _HistoryPayload()
    candidates = _read_payload(session_dir / CONST_REVIEW_CANDIDATES_FILENAME)
    profile = ReviewProfile.load(session_dir)
    return ReviewSessionRecord(
        path=session_dir,
        subject_key=subject_key(reported.subject),
        target=profile.target if profile is not None else None,
        generated_at=_parse_generated_at(reported.generated_at),
        findings=tuple(reported.findings),
        raised=tuple((candidates if candidates is not None else reported).findings),
    )


def _read_payload(path: Path) -> _HistoryPayload | None:
    """The history fields of a session file; None when it is missing or cannot be read."""
    if not path.is_file():
        return None
    try:
        return _HistoryPayload.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        logger.debug("Skipping unreadable review session file %s: %s", path, exc)
        return None


def _parse_generated_at(stamp: str) -> datetime | None:
    """When a session was written; a stamp without an offset is local time."""
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    # The persona loop stamped local time without an offset before #607.
    return parsed if parsed.tzinfo is not None else parsed.astimezone()
