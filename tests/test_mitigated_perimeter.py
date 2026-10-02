"""Tests for mitigated findings perimeter tracking, ledger persistence, and diff intersection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.mitigations import (
    MitigatedFindingEntry,
    find_perimeter_changes,
    format_perimeter_warning,
    load_mitigated_findings,
    record_mitigated_finding,
    save_mitigated_findings,
)
from devops_cli.ai.review.verdicts import apply_verdict, assert_verdict_invariants
from devops_cli.ai.review_schema import Finding, ReviewSessionPayload


def test_mitigated_finding_entry_defaults() -> None:
    entry = MitigatedFindingEntry(
        title="SQL injection risk",
        location="src/db.py:42",
        mitigating_mechanism="PreparedStatements",
        perimeter_files=["src/db.py", "src/queries.py"],
        regression_test="tests/test_db_queries.py",
        reason="Queries use parameterized inputs",
    )
    assert (
        entry.title,
        entry.location,
        entry.mitigating_mechanism,
        entry.perimeter_files,
        entry.regression_test,
        entry.recorded_by,
    ) == (
        "SQL injection risk",
        "src/db.py:42",
        "PreparedStatements",
        ["src/db.py", "src/queries.py"],
        "tests/test_db_queries.py",
        "human",
    )


def test_ledger_save_and_load(tmp_path: Path) -> None:
    ledger_file = tmp_path / "mitigated_findings.json"
    assert load_mitigated_findings(ledger_file) == []

    entries = [
        MitigatedFindingEntry(
            title="SSRF in fetcher",
            location="src/fetch.py:10",
            mitigating_mechanism="IPFilter",
            perimeter_files=["src/fetch.py"],
        ),
    ]
    save_mitigated_findings(entries, ledger_file)
    loaded = load_mitigated_findings(ledger_file)

    assert (len(loaded), loaded[0].title, loaded[0].mitigating_mechanism) == (
        1,
        "SSRF in fetcher",
        "IPFilter",
    )


def test_record_mitigated_finding_new_and_update(tmp_path: Path) -> None:
    ledger_file = tmp_path / "mitigated_findings.json"
    finding = Finding(
        title="Path traversal vulnerability",
        location="src/reader.py:15",
        severity="HIGH",
        status="MITIGATED",
        perimeter_files=["src/reader.py"],
    )

    recorded = record_mitigated_finding(
        finding,
        reason="Resolved path checked with is_relative_to",
        perimeter_files=["src/reader.py", "src/fs.py"],
        regression_test="tests/test_reader.py",
        ledger_path=ledger_file,
    )

    assert (
        recorded.title,
        recorded.perimeter_files,
        recorded.regression_test,
    ) == (
        "Path traversal vulnerability",
        ["src/reader.py", "src/fs.py"],
        "tests/test_reader.py",
    )

    # Updating existing finding
    updated = record_mitigated_finding(
        finding,
        reason="Updated rationale",
        perimeter_files=["src/reader.py", "src/fs.py", "src/utils.py"],
        regression_test="tests/test_reader.py",
        ledger_path=ledger_file,
    )

    all_entries = load_mitigated_findings(ledger_file)
    assert (len(all_entries), updated.perimeter_files) == (
        1,
        ["src/reader.py", "src/fs.py", "src/utils.py"],
    )


def test_find_perimeter_changes_intersection(tmp_path: Path) -> None:
    ledger_file = tmp_path / "mitigated_findings.json"
    entries = [
        MitigatedFindingEntry(
            title="Memory leak in worker",
            location="src/worker.py:50",
            mitigating_mechanism="BoundedQueue",
            perimeter_files=["src/worker.py", "src/queue.py"],
        ),
        MitigatedFindingEntry(
            title="Auth bypass",
            location="src/auth.py:20",
            mitigating_mechanism="JWTVerifier",
            perimeter_files=["src/auth.py"],
        ),
    ]
    save_mitigated_findings(entries, ledger_file)

    # Diff modifying src/worker.py
    changed_diff = ["src/worker.py", "docs/README.md"]
    matches = find_perimeter_changes(changed_diff, ledger_file)

    assert (len(matches), matches[0][0].title, matches[0][1]) == (
        1,
        "Memory leak in worker",
        ["src/worker.py"],
    )

    # Diff not touching perimeter files
    no_matches = find_perimeter_changes(["docs/README.md", "src/other.py"], ledger_file)
    assert no_matches == []


def test_format_perimeter_warning() -> None:
    entries_matches = [
        (
            MitigatedFindingEntry(
                title="Memory leak in worker",
                location="src/worker.py:50",
                mitigating_mechanism="BoundedQueue",
                perimeter_files=["src/worker.py"],
            ),
            ["src/worker.py"],
        )
    ]
    warning_text = format_perimeter_warning(entries_matches)
    assert (
        "1 mitigated finding whose perimeter changed" in warning_text,
        "Memory leak in worker" in warning_text,
        "src/worker.py" in warning_text,
    ) == (True, True, True)


def test_invalidated_cannot_have_mitigated_true() -> None:
    f = Finding(
        title="Hallucinated issue",
        location="src/mod.py:1",
        severity="LOW",
        status="INVALIDATED",
        verified=False,
        reportable=False,
        mitigated=True,
    )
    with pytest.raises(AssertionError, match="cannot have mitigated=True"):
        assert_verdict_invariants([f])


def test_apply_verdict_mitigated_fields() -> None:
    f = Finding(
        title="Flaky timeout",
        location="src/client.py:100",
        severity="MEDIUM",
        status="UNVERIFIED",
    )
    updated = apply_verdict(
        f,
        "MITIGATED",
        by="human",
        reason="Exponential backoff added",
        mitigating_mechanism="ExponentialBackoff",
        perimeter_files=["src/client.py", "src/retry.py"],
        regression_test="tests/test_retry.py",
    )

    assert (
        updated.status,
        updated.reportable,
        updated.mitigated,
        updated.mitigating_mechanism,
        updated.perimeter_files,
        updated.regression_test,
    ) == (
        "MITIGATED",
        True,
        True,
        "ExponentialBackoff",
        ["src/client.py", "src/retry.py"],
        "tests/test_retry.py",
    )


def test_cli_verify_finding_mitigated(tmp_path: Path) -> None:
    from devops_cli.commands.review import app

    runner = CliRunner()
    session_dir = tmp_path / "review_session_001"
    session_dir.mkdir(parents=True)
    findings_file = session_dir / "findings.json"

    from devops_cli.ai.review_schema import SavedFinding

    f = SavedFinding(
        title="Unchecked allocation",
        location="src/alloc.py:22",
        severity="HIGH",
        status="UNVERIFIED",
    )
    payload = ReviewSessionPayload(findings=[f])
    findings_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    ledger_file = tmp_path / "mitigated_findings.json"

    with (
        patch(
            "devops_cli.commands.review._find_session_dir",
            return_value=session_dir,
        ),
        patch(
            "devops_cli.ai.review.mitigations.DEFAULT_MITIGATIONS_LEDGER_PATH",
            ledger_file,
        ),
    ):
        # 1. Calling with invalid status should fail
        res_fail = runner.invoke(
            app,
            ["verify", "001", "--index", "1", "--status", "NONEXISTENT_STATUS"],
        )
        assert res_fail.exit_code == 1

        # 2. Calling with --perimeter and --reason succeeds
        res_ok = runner.invoke(
            app,
            [
                "verify",
                "001",
                "--index",
                "1",
                "--status",
                "MITIGATED",
                "--reason",
                "Bounded allocator limit",
                "--perimeter",
                "src/alloc.py",
                "--regression-test",
                "tests/test_alloc.py",
            ],
        )
        assert res_ok.exit_code == 0

    saved_payload = ReviewSessionPayload.model_validate_json(
        findings_file.read_text(encoding="utf-8")
    )
    saved_finding = saved_payload.findings[0]
    ledger_entries = load_mitigated_findings(ledger_file)

    assert (
        saved_finding.status,
        saved_finding.mitigated,
        saved_finding.reportable,
        saved_finding.perimeter_files,
        saved_finding.regression_test,
        len(ledger_entries),
    ) == (
        "MITIGATED",
        True,
        True,
        ["src/alloc.py"],
        "tests/test_alloc.py",
        1,
    )


def test_pr_check_perimeter_warning(tmp_path: Path) -> None:
    from devops_cli.commands.pr import ChangedFile, _ChangedFilesRead, _check_pr_perimeter_changes

    ledger_file = tmp_path / "mitigated_findings.json"
    entries = [
        MitigatedFindingEntry(
            title="Resource leak",
            location="src/res.py:10",
            mitigating_mechanism="ContextManager",
            perimeter_files=["src/res.py"],
        ),
    ]
    save_mitigated_findings(entries, ledger_file)

    with (
        patch(
            "devops_cli.ai.review.mitigations.DEFAULT_MITIGATIONS_LEDGER_PATH",
            ledger_file,
        ),
        patch("devops_cli.commands.pr.print_warning") as mock_warn,
    ):
        _check_pr_perimeter_changes(_ChangedFilesRead([ChangedFile("src/res.py", "modified")]))
        assert mock_warn.called
        assert "Resource leak" in str(mock_warn.call_args[0][0])
