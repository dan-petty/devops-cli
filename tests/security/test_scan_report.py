"""The scan report: the pipeline that builds it, and the `devops scan report` and
`devops scan sarif` commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_SARIF_VERSION,
    CONST_SEVERITY_ORDER,
)
from devops_cli.security.pipeline import build_report, report_from_findings
from devops_cli.security.sarif import (
    write_sarif,
)
from devops_cli.security.suppression import (
    load_policy,
)
from tests.support.builders import make_normalized_finding
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def test_a_report_deduplicates_and_correlates_scanner_output(tmp_path: Path) -> None:
    """The whole point of the pipeline is one coherent result rather than N tables."""
    results = {
        "bandit": [
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
        ],
        "semgrep": [
            Finding(severity="HIGH", location="src/app.py:4", title="[S1] shell true"),
        ],
    }
    report = build_report(results, tmp_path)
    assert (report.total, report.duplicates_removed, len(report.clusters)) == (2, 1, 1)


def test_a_report_counts_every_severity(tmp_path: Path) -> None:
    """A missing key would be read as a severity that was never checked."""
    report = build_report({"bandit": []}, tmp_path)
    assert report.counts == dict.fromkeys(CONST_SEVERITY_ORDER, 0)


def test_suppression_is_applied_before_deduplication(tmp_path: Path) -> None:
    """The suppressed list must name every occurrence hidden, not just the first.

    Reporting one suppression where a rule silenced four understates what the policy does.
    """
    policy_file = tmp_path / "p.yml"
    policy_file.write_text("suppressions:\n  - rule: B602\n")
    policy = load_policy(policy_file)
    results = {
        "bandit": [
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
            Finding(severity="HIGH", location="src/app.py:4", title="[B602] shell true"),
        ]
    }
    report = build_report(results, tmp_path, policy=policy)
    assert (report.total, len(report.suppressed)) == (0, 2)


def test_a_minimum_severity_filters_the_report(tmp_path: Path) -> None:
    """A noisy INFO stream drowns the findings that matter."""
    results = {
        "bandit": [
            Finding(severity="INFO", location="a.py:1", title="[I1] minor"),
            Finding(severity="CRITICAL", location="b.py:2", title="[C1] severe"),
        ]
    }
    report = build_report(results, tmp_path, min_severity="HIGH")
    assert [finding.rule_id for finding in report.findings] == ["C1"]


def test_a_report_identifies_its_most_severe_finding(tmp_path: Path) -> None:
    """The gate threshold is evaluated against this."""
    results = {
        "bandit": [
            Finding(severity="LOW", location="a.py:1", title="[L] minor"),
            Finding(severity="CRITICAL", location="b.py:2", title="[C] severe"),
        ]
    }
    assert build_report(results, tmp_path).highest_severity() == "CRITICAL"


def test_an_empty_report_has_no_highest_severity(tmp_path: Path) -> None:
    """A clean scan must not be reported as having a severity."""
    assert build_report({"bandit": []}, tmp_path).highest_severity() is None


@pytest.mark.parametrize(
    ("severity", "threshold", "expected"),
    [
        ("CRITICAL", "HIGH", True),
        ("HIGH", "HIGH", True),
        ("MEDIUM", "HIGH", False),
        ("INFO", "INFO", True),
    ],
)
def test_the_gate_threshold_is_inclusive(
    severity: str, threshold: str, expected: bool, tmp_path: Path
) -> None:
    """A gate set at HIGH must fail on a HIGH finding, not only above it."""
    results = {"bandit": [Finding(severity=severity, location="a.py:1", title="[R] issue")]}
    assert build_report(results, tmp_path).exceeds(threshold) is expected


def test_an_empty_report_never_trips_the_gate(tmp_path: Path) -> None:
    """A clean scan must not fail the build."""
    assert build_report({"bandit": []}, tmp_path).exceeds("INFO") is False


def test_a_report_serializes_for_json_consumers(tmp_path: Path) -> None:
    """Machine consumers need the counts, the clusters and the fingerprints."""
    results = {"bandit": [Finding(severity="HIGH", location="a.py:1", title="[B1] issue")]}
    payload = build_report(results, tmp_path).as_dict()
    assert (payload["total"], payload["tools"], payload["counts"]["HIGH"]) == (
        1,
        ["bandit"],
        1,
    )


def test_a_report_can_be_built_from_ingested_sarif() -> None:
    """An imported document flows through the same suppression and ranking."""
    report = report_from_findings(
        [make_normalized_finding(), make_normalized_finding(line=90)], "imported.sarif"
    )
    assert (report.total, report.duplicates_removed) == (1, 1)


def test_the_report_command_renders_correlated_findings(
    tmp_path: Path, cli: Callable[..., Any], scanner_fake: ScannerFake
) -> None:
    """The command is the pipeline's only user-facing surface."""
    bandit_output = {
        "results": [
            {
                "test_id": "B602",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "shell true",
                "line_number": 4,
                "filename": "a.py",
            }
        ]
    }
    scanner_fake.script("bandit", ToolAnswer(stdout=json.dumps(bandit_output), exit_code=0))
    result = cli(["scan", "report", str(tmp_path), "--scanner", "bandit"])
    assert (result.exit_code, "B602" in result.stdout) == (0, True)


def test_the_report_command_rejects_an_unknown_scanner(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """A typo must not silently scan with nothing and report success."""
    result = cli(["scan", "report", str(tmp_path), "--scanner", "nosuchtool"])
    assert result.exit_code == 2


def test_the_report_command_fails_the_build_on_a_severe_finding(
    tmp_path: Path, cli: Callable[..., Any], scanner_fake: ScannerFake
) -> None:
    """The gate is what makes the command usable in CI."""
    bandit_output = {
        "results": [
            {
                "test_id": "C1",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "severe",
                "line_number": 4,
                "filename": "a.py",
            }
        ]
    }
    scanner_fake.script("bandit", ToolAnswer(stdout=json.dumps(bandit_output), exit_code=0))
    result = cli(["scan", "report", str(tmp_path), "--scanner", "bandit", "--fail-on", "HIGH"])
    assert result.exit_code == 1


def test_the_report_command_passes_when_nothing_meets_the_gate(
    tmp_path: Path, cli: Callable[..., Any], scanner_fake: ScannerFake
) -> None:
    """A gate that always fails is a gate nobody keeps."""
    bandit_output = {
        "results": [
            {
                "test_id": "L1",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "issue_text": "minor",
                "line_number": 4,
                "filename": "a.py",
            }
        ]
    }
    scanner_fake.script("bandit", ToolAnswer(stdout=json.dumps(bandit_output), exit_code=0))
    result = cli(["scan", "report", str(tmp_path), "--scanner", "bandit", "--fail-on", "HIGH"])
    assert result.exit_code == 0


def test_the_report_command_writes_sarif(
    tmp_path: Path, cli: Callable[..., Any], scanner_fake: ScannerFake
) -> None:
    """Exporting is how findings reach GitHub code scanning."""
    bandit_output = {
        "results": [
            {
                "test_id": "B602",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "shell true",
                "line_number": 4,
                "filename": "a.py",
            }
        ]
    }
    scanner_fake.script("bandit", ToolAnswer(stdout=json.dumps(bandit_output), exit_code=0))
    destination = tmp_path / "out.sarif"
    result = cli(
        ["scan", "report", str(tmp_path), "--scanner", "bandit", "--sarif", str(destination)]
    )
    document = json.loads(destination.read_text())
    assert (result.exit_code, document["version"]) == (0, CONST_SARIF_VERSION)


def test_a_failing_scanner_does_not_discard_the_others(
    tmp_path: Path, cli: Callable[..., Any], scanner_fake: ScannerFake
) -> None:
    """One broken tool must not lose every other tool's findings."""
    bandit_output = {
        "results": [
            {
                "test_id": "B602",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "shell true",
                "line_number": 4,
                "filename": "a.py",
            }
        ]
    }
    scanner_fake.script("bandit", ToolAnswer(stdout=json.dumps(bandit_output), exit_code=0))
    scanner_fake.script("semgrep", ToolAnswer(exit_code=1, stderr="scanner crashed"))
    result = cli(["scan", "report", str(tmp_path), "--scanner", "bandit,semgrep", "--json"])
    assert (result.exit_code, "B602" in result.stdout) == (0, True)


def test_the_sarif_command_ingests_a_document(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Third-party SARIF joins the same report."""
    destination = write_sarif([make_normalized_finding()], tmp_path / "in.sarif")
    result = cli(["scan", "sarif", str(destination)])
    assert (result.exit_code, "B602" in result.stdout) == (0, True)


def test_the_sarif_command_rejects_a_document_that_is_not_sarif(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Reporting a clean scan for an unreadable document is the dangerous outcome."""
    path = tmp_path / "bad.sarif"
    path.write_text('{"version": "1.0.0"}')
    result = cli(["scan", "sarif", str(path)])
    assert result.exit_code == 2


def test_the_sarif_command_applies_a_suppression_policy(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Suppression applies equally to ingested findings."""
    destination = write_sarif([make_normalized_finding()], tmp_path / "in.sarif")
    policy = tmp_path / "p.yml"
    policy.write_text("suppressions:\n  - rule: B602\n")
    result = cli(["scan", "sarif", str(destination), "--suppress", str(policy), "--json"])
    payload = json.loads(result.stdout)
    assert (result.exit_code, payload["total"], payload["suppressed"]) == (0, 0, 1)


def test_an_unreadable_suppression_policy_stops_the_scan(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Continuing without the policy reports findings the operator believes are accepted."""
    destination = write_sarif([make_normalized_finding()], tmp_path / "in.sarif")
    result = cli(
        ["scan", "sarif", str(destination), "--suppress", str(tmp_path / "absent.yml")],
    )
    assert result.exit_code == 2
