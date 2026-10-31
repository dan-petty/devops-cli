"""Review session fixtures for review history and session tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from devops_cli.review.session import ReviewSessionStore


@pytest.fixture
def review_store(isolate_data_dir: Path) -> type[ReviewSessionStore]:
    """The review session store, rooted in the test's own data directory with its root created
    (#771). Naming `ReviewSessionStore.root()` creates nothing, as a review that has not yet
    written a session finds it, so a test that lists or searches sessions asks for the store."""
    from devops_cli.review.session import ReviewSessionStore

    ReviewSessionStore.root().mkdir(parents=True)
    return ReviewSessionStore


@pytest.fixture
def write_review_session() -> Callable[..., Path]:
    """Write a published review session as the pipeline lays one out: findings.json, plus
    candidates.json and a profile.json naming `target` when they are given.

    Review history, baseline and stats tests share it.
    """
    from devops_cli.ai.review.profile import ReviewProfile
    from devops_cli.ai.review_schema import ReviewSessionPayload
    from devops_cli.review.session import ReviewSession

    def write(
        session_dir: Path,
        *,
        generated_at: str,
        subject: dict[str, str] | None = None,
        findings: Sequence[Any] = (),
        candidates: Sequence[Any] | None = None,
        target: str | None = None,
    ) -> Path:
        session = ReviewSession(session_dir)

        def payload(saved: Sequence[Any]) -> ReviewSessionPayload:
            return ReviewSessionPayload(
                generated_at=generated_at, subject=subject or {}, findings=list(saved)
            )

        session.write_findings(payload(findings))
        if candidates is not None:
            session.write_raised(payload(candidates))
        if target is not None:
            session.write_profile(ReviewProfile(session_id=session_dir.name, target=target))
        return session.publish()

    return write


@pytest.fixture
def review_history(tmp_path: Path, write_review_session: Callable[..., Path]) -> Path:
    """A reviews directory with three sessions of one subject, a target-only session, an unkeyed
    session, and a directory without findings.json.

    `same-3` is the newest of the subject and counts. With it left out, `same-1`, whose finding
    has a verdict, outranks the newer `same-2`, whose finding has none. Each session reports one
    finding, so counting every session and counting each subject once give different tables.
    """
    from devops_cli.ai.review.history import review_subject
    from devops_cli.ai.review_schema import SavedFinding

    reviews = tmp_path / "reviews"
    subject = review_subject("path", "/repo/src", ["diff --git a/mod.py b/mod.py\n"])
    sessions = (
        ("same-1", "2026-10-01T09:00:00+00:00", subject, "VERIFIED", None),
        ("same-2", "2026-10-01T10:00:00+00:00", subject, "UNVERIFIED", None),
        ("same-3", "2026-10-01T11:00:00+00:00", subject, "VERIFIED", None),
        ("target-only", "2026-09-30T09:00:00+00:00", None, "INVALIDATED", "/repo/src"),
        ("unkeyed", "2026-09-29T09:00:00", None, "MITIGATED", None),
    )
    for name, generated_at, session_subject, status, target in sessions:
        finding = SavedFinding(
            title=f"{name} finding",
            location="mod.py:1",
            status=status,
            persona="devsecops",
        )
        write_review_session(
            reviews / name,
            generated_at=generated_at,
            subject=session_subject,
            findings=[finding],
            target=target,
        )
    (reviews / "incomplete" / "files").mkdir(parents=True)
    return reviews
