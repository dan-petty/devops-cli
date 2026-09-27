"""Unified verdict writer and structural invariant enforcement for review findings."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from devops_cli.ai.review_schema import Finding, SavedFinding

VerifiedBy = Literal[
    "criteria",
    "llm",
    "debate",
    "human",
    "deterministic:syntax_error",
    "deterministic:missing_symbol",
    "deterministic:missing_header",
    "deterministic:pathlib_resolve",
    "deterministic:scanned_clean_dependency",
    "deterministic:placeholder_advisory",
    "deterministic:unsupported_runtime",
    "deterministic:operational_protocol",
    "deterministic:test_fixture_credential",
    "deterministic:uninitialized_variable",
    "deterministic:conversational_monologue",
    "deterministic:benign_compliment",
    "deterministic:masked_placeholder_syntax_error",
    "deterministic:none_dereference",
    "deterministic:catalog_hallucination",
    "deterministic:verdict_polarity",
    "deterministic:construct_location",
    "deterministic:line_boundaries",
    "deterministic:dry_run",
    "deterministic:vulnerable_dependency",
]

_VALID_STATUSES: frozenset[str] = frozenset({"VERIFIED", "INVALIDATED", "MITIGATED", "UNVERIFIED"})


def _check_invalidated_invariants(f: Finding | SavedFinding) -> None:
    if f.reportable or f.verified:
        raise AssertionError(
            f"Invariant violation: INVALIDATED finding must be neither reportable nor verified: {f.title}"
        )
    if getattr(f, "mitigated", False):
        raise AssertionError(
            f"Invariant violation: INVALIDATED finding cannot have mitigated=True: {f.title}"
        )


def _check_verified_invariants(f: Finding | SavedFinding) -> None:
    if not f.verified:
        raise AssertionError(
            f"Invariant violation: VERIFIED finding must have verified=True: {f.title}"
        )
    if not getattr(f, "verified_by", None):
        raise AssertionError(
            f"Invariant violation: VERIFIED finding requires non-empty verified_by: {f.title}"
        )


def _check_unverified_invariants(f: Finding | SavedFinding) -> None:
    if f.verified:
        raise AssertionError(
            f"Invariant violation: UNVERIFIED finding must have verified=False: {f.title}"
        )
    if getattr(f, "verified_by", None) is not None:
        raise AssertionError(
            f"Invariant violation: UNVERIFIED finding must have verified_by=None: {f.title}"
        )


def _check_mitigated_invariants(f: Finding | SavedFinding) -> None:
    if not f.reportable:
        raise AssertionError(
            f"Invariant violation: MITIGATED finding must stay reportable: {f.title}"
        )


_INVARIANT_CHECKERS = {
    "INVALIDATED": _check_invalidated_invariants,
    "VERIFIED": _check_verified_invariants,
    "UNVERIFIED": _check_unverified_invariants,
    "MITIGATED": _check_mitigated_invariants,
}


def assert_verdict_invariants(findings: Sequence[Finding | SavedFinding]) -> None:
    """Enforce verdict invariants across findings.

    Invariants:
    1. INVALIDATED is neither reportable nor verified.
    2. VERIFIED requires verified_by.
    3. UNVERIFIED has neither verified nor verified_by.
    4. MITIGATED stays reportable.
    """
    for f in findings:
        status = getattr(f, "status", None)
        if isinstance(status, str):
            checker = _INVARIANT_CHECKERS.get(status.upper().strip())
            if checker is not None:
                checker(f)


def _build_verdict_updates(
    status: str,
    by: str | None,
    reason: str | None,
    now_iso: str,
    citation_line: int | None,
    mitigating_mechanism: str | None,
    verification_note: str | None,
    perimeter_files: list[str] | None = None,
    regression_test: str | None = None,
) -> dict[str, Any]:
    """Compute structural update dictionary for the given status."""
    if status == "INVALIDATED":
        return {
            "status": "INVALIDATED",
            "verified": False,
            "reportable": False,
            "mitigated": False,
            "verified_by": by,
            "verified_at": now_iso,
            "invalidation_reason": reason,
            "citation_line": citation_line,
            "mitigating_mechanism": mitigating_mechanism,
            "verification_note": verification_note,
        }
    if status == "VERIFIED":
        if not by or not str(by).strip():
            raise ValueError("VERIFIED status requires a non-empty verified_by adjudicator")
        return {
            "status": "VERIFIED",
            "verified": True,
            "reportable": True,
            "mitigated": False,
            "verified_by": by,
            "verified_at": now_iso,
            "invalidation_reason": None,
            "citation_line": citation_line,
            "verification_note": verification_note,
        }
    if status == "UNVERIFIED":
        return {
            "status": "UNVERIFIED",
            "verified": False,
            "reportable": True,
            "mitigated": False,
            "verified_by": None,
            "verified_at": None,
            "invalidation_reason": reason,
            "citation_line": citation_line,
            "verification_note": verification_note,
        }
    # MITIGATED
    return {
        "status": "MITIGATED",
        "verified": True,
        "reportable": True,
        "mitigated": True,
        "verified_by": by,
        "verified_at": now_iso,
        "invalidation_reason": reason,
        "citation_line": citation_line,
        "mitigating_mechanism": mitigating_mechanism,
        "perimeter_files": perimeter_files or [],
        "regression_test": regression_test,
        "verification_note": verification_note,
    }


def apply_verdict[T: (Finding, SavedFinding)](
    finding: T,
    status: str,
    by: str | None,
    reason: str | None = None,
    *,
    citation_line: int | None = None,
    mitigating_mechanism: str | None = None,
    perimeter_files: list[str] | None = None,
    regression_test: str | None = None,
    verification_note: str | None = None,
    confidence_score: float | None = None,
    verified_at: str | None = None,
    **extra_updates: Any,
) -> T:
    """Apply a unified adjudication verdict to a finding, maintaining core invariants."""
    norm_status = status.upper().strip()
    if norm_status not in _VALID_STATUSES:
        raise ValueError(f"Invalid finding status: {status!r}. Must be one of {_VALID_STATUSES}")

    now_iso = verified_at or datetime.now(UTC).isoformat()
    updates = _build_verdict_updates(
        status=norm_status,
        by=by,
        reason=reason,
        now_iso=now_iso,
        citation_line=citation_line,
        mitigating_mechanism=mitigating_mechanism,
        verification_note=verification_note,
        perimeter_files=perimeter_files,
        regression_test=regression_test,
    )

    if confidence_score is not None:
        updates["confidence_score"] = confidence_score

    for key, val in extra_updates.items():
        if val is not None:
            updates[key] = val

    for key, val in updates.items():
        if hasattr(finding, key):
            setattr(finding, key, val)

    assert_verdict_invariants([finding])
    return finding
