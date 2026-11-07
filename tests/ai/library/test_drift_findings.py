"""`LibraryDriftAuditor.audit_workspace`: the calls it flags against a library contract (#1329)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.library.drift_auditor import DriftIssueType, DriftReport, LibraryDriftAuditor
from tests.support.library_contracts import write_demo_contract, write_demo_workspace


def _audit(tmp_path: Path, source: str) -> DriftReport:
    """Audit a workspace of one file of `source` against the demo contract."""
    contracts_dir = tmp_path / "libraries"
    write_demo_contract(contracts_dir)
    workspace = write_demo_workspace(tmp_path, source)
    return LibraryDriftAuditor(contracts_dir=contracts_dir).audit_workspace(workspace)


def test_a_call_that_matches_the_contract_is_clean(tmp_path: Path) -> None:
    report = _audit(
        tmp_path,
        'from demolib import compute\n\ndef run():\n    return compute(x=10, mode="turbo")\n',
    )

    assert (report.files_scanned, report.breaking_count, report.findings) == (1, 0, [])


def test_a_call_of_a_removed_function_is_a_breaking_finding(tmp_path: Path) -> None:
    report = _audit(
        tmp_path,
        "from demolib import nonexistent_function\n\n"
        "def run():\n    return nonexistent_function(123)\n",
    )

    finding = next(f for f in report.findings if f.symbol == "nonexistent_function")
    assert (finding.issue_type, finding.is_breaking, report.breaking_count >= 1) == (
        DriftIssueType.REMOVED_METHOD,
        True,
        True,
    )


def test_a_keyword_the_contract_does_not_know_is_a_breaking_finding(tmp_path: Path) -> None:
    report = _audit(
        tmp_path,
        "from demolib import compute\n\ndef run():\n    return compute(x=10, invalid_parameter=99)\n",
    )

    finding = next(f for f in report.findings if "invalid_parameter" in f.message)
    assert (finding.issue_type, finding.is_breaking) == (DriftIssueType.UNRECOGNIZED_KWARG, True)


def test_a_call_of_a_deprecated_function_is_a_warning(tmp_path: Path) -> None:
    report = _audit(
        tmp_path,
        "from demolib import legacy_calc\n\ndef run():\n    return legacy_calc(val=42)\n",
    )

    finding = next(f for f in report.findings if f.symbol == "legacy_calc")
    assert (finding.issue_type, finding.is_breaking, report.warning_count >= 1) == (
        DriftIssueType.DEPRECATED_CALL,
        False,
        True,
    )


def test_a_call_through_a_module_import_or_an_alias_is_checked(tmp_path: Path) -> None:
    report = _audit(
        tmp_path,
        "import demolib\nimport demolib as d\n\n"
        "def run():\n"
        '    a = demolib.compute(x=10, mode="turbo")\n'
        "    b = d.legacy_calc(val=99)\n"
        "    return a, b\n",
    )

    assert (
        report.files_scanned,
        report.total_calls_checked >= 2,
        [f.symbol for f in report.findings],
    ) == (1, True, ["legacy_calc"])


def test_a_function_imported_under_an_alias_is_checked(tmp_path: Path) -> None:
    report = _audit(
        tmp_path,
        "from demolib import legacy_calc as old\n\ndef run():\n    return old(val=42)\n",
    )

    assert [(f.symbol, f.issue_type) for f in report.findings] == [
        ("legacy_calc", DriftIssueType.DEPRECATED_CALL)
    ]


def test_a_file_that_does_not_parse_is_counted_and_skipped(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "libraries"
    write_demo_contract(contracts_dir)
    workspace = write_demo_workspace(tmp_path, "import demolib\ndemolib.compute(x=1)\n", "ok.py")
    (workspace / "syntax_error.py").write_text("def broken_syntax(:\n", encoding="utf-8")

    report = LibraryDriftAuditor(contracts_dir=contracts_dir).audit_workspace(workspace)

    assert (report.files_scanned, report.total_calls_checked >= 1, report.breaking_count) == (
        2,
        True,
        0,
    )
