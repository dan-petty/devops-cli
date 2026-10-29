"""The `--fail-on` gate of a scan report, as data: `gate_report` (#2543)."""

from __future__ import annotations

import pytest

from devops_cli.security.base import ScanOutcome
from devops_cli.security.pipeline import GateVerdict, ScanReport, gate_report
from tests.support.builders import make_normalized_finding


def _report(*, severity: str | None = None, **statuses: str) -> ScanReport:
    """A report with one outcome per scanner name, and one gating finding of `severity`."""
    findings = [make_normalized_finding(severity=severity)] if severity else []
    outcomes = {
        name: ScanOutcome(status=status, findings=[], reason="")
        for name, status in statuses.items()
    }
    return ScanReport(target="src", findings=findings, outcomes=outcomes)


@pytest.mark.parametrize(
    ("report", "fail_on", "explicit", "verdict"),
    [
        pytest.param(
            _report(severity="CRITICAL", bandit="failed"),
            None,
            ["absent"],
            GateVerdict(),
            id="no-threshold",
        ),
        pytest.param(
            _report(bandit="ran", semgrep="built-in patterns"),
            "HIGH",
            ["bandit", "semgrep"],
            GateVerdict(),
            id="clean",
        ),
        pytest.param(
            _report(semgrep="failed", bandit="failed"),
            "HIGH",
            None,
            GateVerdict(failed_scanners=("bandit", "semgrep")),
            id="failed-scanners",
        ),
        pytest.param(
            _report(bandit="ran", trivy="unavailable"),
            "HIGH",
            ["trivy", "gitleaks", "bandit"],
            GateVerdict(scanners_not_run=("gitleaks", "trivy")),
            id="named-not-run",
        ),
        pytest.param(
            _report(severity="HIGH", bandit="ran"),
            "HIGH",
            None,
            GateVerdict(exceeds_threshold=True),
            id="at-threshold",
        ),
        pytest.param(
            _report(severity="MEDIUM", bandit="ran"),
            "HIGH",
            None,
            GateVerdict(),
            id="below-threshold",
        ),
    ],
)
def test_the_gate_names_each_reason_a_report_fails(
    report: ScanReport, fail_on: str | None, explicit: list[str] | None, verdict: GateVerdict
) -> None:
    """With no threshold every report passes; with one, failed scanners, named scanners that did
    not run and a finding at or above it each fail the gate."""
    result = gate_report(report, fail_on=fail_on, explicit_scanners=explicit)
    assert (result, result.passed) == (verdict, verdict == GateVerdict())


def test_a_finding_that_does_not_gate_passes_at_any_threshold() -> None:
    report = ScanReport(
        target="src", findings=[make_normalized_finding(severity="CRITICAL", gating=False)]
    )
    assert gate_report(report, fail_on="LOW").passed is True
