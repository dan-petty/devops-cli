"""Admission gate and constructor for frozen review findings (#871).

A frozen Finding is constructed exclusively by `admit()` in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from devops_cli.ai.review.path_classes import classify_path
from devops_cli.review.anchors import AdvisoryAnchor, ToolAnchor
from devops_cli.review.finding import Finding
from devops_cli.review.fingerprint import compute_fingerprint_v2
from devops_cli.review.location import validate_location
from devops_cli.review.severity import derive_severity
from devops_cli.review.state import FindingState
from devops_cli.review.suppression import (
    ReviewSuppression,
    check_inline_marker_in_diff,
)


def _record_rejection(counts: dict[str, int] | None, reason: str) -> None:
    """Record a typed rejection count into the tracking dictionary."""
    if counts is not None:
        counts[reason] = counts.get(reason, 0) + 1


def _check_suppressions(
    *,
    suppressions: Sequence[ReviewSuppression] | None,
    rule_id: str,
    path: str,
    fingerprint: str,
    line: int | None,
    added_diff_lines: set[tuple[str, int]] | None,
    file_content: str | None,
) -> tuple[FindingState, str | None, str | None, bool]:
    """Evaluate review.toml suppressions and inline markers.

    Returns:
        (state, suppression_reason, suppression_expiry, suppressed_by_change)
    """
    if suppressions:
        for supp in suppressions:
            if supp.matches(rule_id=rule_id, path=path, fingerprint=fingerprint):
                return FindingState.SUPPRESSED, supp.reason, supp.expiry, False

    if line is not None and file_content:
        file_lines = file_content.splitlines()
        has_marker, added_by_change = check_inline_marker_in_diff(
            path, line, added_diff_lines or set(), file_lines
        )
        if has_marker:
            if added_by_change:
                return FindingState.OPEN, "Inline marker added by change", None, True
            return (
                FindingState.SUPPRESSED,
                "Inline suppression marker at base revision",
                None,
                False,
            )

    return FindingState.OPEN, None, None, False


def admit(
    *,
    anchor: ToolAnchor | AdvisoryAnchor | None,
    tool: str,
    rule_id: str,
    path: str,
    message: str,
    line: int | None = None,
    end_line: int | None = None,
    symbol: str | None = None,
    logical_location: str | None = None,
    tool_version: str | None = None,
    description: str = "",
    fix: str = "",
    rule_severity: str | None = None,
    sarif_level: str | None = None,
    security_severity: float | int | str | None = None,
    worktree_root: Path | None = None,
    commit_files: set[str],
    file_content_getter: Callable[[str], str | None] | None = None,
    manifest_objects: set[str] | None = None,
    lockfile_packages: set[str] | None = None,
    path_classes: Mapping[str, Sequence[str]] | None = None,
    severity_caps: Mapping[str, str] | None = None,
    suppressions: Sequence[ReviewSuppression] | None = None,
    added_diff_lines: set[tuple[str, int]] | None = None,
    base_fingerprints: set[str] | None = None,
    tool_ran: bool = True,
    file_scanned: bool = True,
    canary_passed: bool = True,
    rejection_counts: dict[str, int] | None = None,
    partial_fingerprints: dict[str, str] | None = None,
    properties: dict[str, Any] | None = None,
) -> Finding | None:
    """Admit a candidate finding into the review, constructing a frozen Finding.

    Returns None if any admission check fails, recording the typed rejection.
    """
    if anchor is None or not anchor.recheck():
        _record_rejection(rejection_counts, "no-anchor")
        return None

    if not tool_ran:
        _record_rejection(rejection_counts, "tool-not-run")
        return None

    if not file_scanned:
        _record_rejection(rejection_counts, "file-not-scanned")
        return None

    if not canary_passed:
        _record_rejection(rejection_counts, "canary-failed")
        return None

    loc_res = validate_location(
        path=path,
        start_line=line,
        end_line=end_line,
        logical_location=logical_location,
        worktree_root=worktree_root,
        commit_files=commit_files,
        file_content_getter=file_content_getter,
        manifest_objects=manifest_objects,
        lockfile_packages=lockfile_packages,
    )
    if not loc_res.valid:
        _record_rejection(rejection_counts, loc_res.rejection_reason or "path-not-in-commit")
        return None

    p_class = classify_path(loc_res.normalized_path, path_classes) if path_classes else None
    eff_sev, derivation = derive_severity(
        security_severity=security_severity,
        rule_severity=rule_severity,
        sarif_level=sarif_level,
        path_class=p_class,
        severity_caps=severity_caps,
    )

    file_content = (
        file_content_getter(loc_res.normalized_path)
        if file_content_getter and loc_res.normalized_path
        else None
    )

    fp_v2 = compute_fingerprint_v2(
        tool=tool,
        rule_id=rule_id,
        path=loc_res.normalized_path,
        start_line=loc_res.start_line,
        file_content=file_content,
        enclosing_symbol=symbol,
        logical_location=loc_res.logical_location,
    )

    state, supp_reason, supp_expiry, supp_by_change = _check_suppressions(
        suppressions=suppressions,
        rule_id=rule_id,
        path=loc_res.normalized_path,
        fingerprint=fp_v2,
        line=loc_res.start_line,
        added_diff_lines=added_diff_lines,
        file_content=file_content,
    )

    is_preexisting = bool(base_fingerprints and fp_v2 in base_fingerprints)
    baseline_state = "unchanged" if is_preexisting else "new"
    introduced = not is_preexisting

    partials = dict(partial_fingerprints or {})
    partials.setdefault("fingerprint_v2", fp_v2)

    return Finding(
        anchor=anchor,
        tool=tool.strip(),
        tool_version=tool_version.strip() if tool_version else None,
        rule_id=rule_id.strip(),
        path=loc_res.normalized_path,
        line=loc_res.start_line,
        end_line=loc_res.end_line,
        symbol=symbol.strip() if symbol else None,
        region_sha256=loc_res.region_sha256,
        logical_location=loc_res.logical_location,
        message=message.strip(),
        description=description.strip(),
        fix=fix.strip(),
        severity=eff_sev,
        severity_derivation=derivation,
        state=state,
        suppression_reason=supp_reason,
        suppression_expiry=supp_expiry,
        suppressed_by_change=supp_by_change,
        confirmed_by=None,
        baseline_state=baseline_state,
        introduced=introduced,
        fingerprint_v2=fp_v2,
        partial_fingerprints=partials,
        properties=dict(properties or {}),
    )
