"""A review report ranks, counts and headlines what was verified (#948).

Session `20261001-224227` reported "563 reportable findings (21 Critical, 263 High)" and headlined
CVE-2021-44228 against a Python CLI. A triage found 46 real defects, none above MEDIUM. The
failures were in code: confidence ranked above verification, the headline named the first
reference of the first-sorted finding, the counts mixed every status, and the analyzer line was a
literal that said "0 critical findings" while three analyzers had failed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import (
    Finding,
    SavedFinding,
    sort_findings,
)
from devops_cli.security.base import ScanOutcome

_NOW = "2026-10-02T12:00:00+00:00"


def _verified(**fields: Any) -> SavedFinding:
    """A finding the verifier confirmed."""
    return SavedFinding(status="VERIFIED", verified=True, verified_by="llm", **fields)


def _executive_summary(report_md: str) -> str:
    """The report's Executive Summary section: the headline and what follows it."""
    return report_md.split("## Executive Summary", 1)[1].split("## Summary of Reportable", 1)[0]


def _orchestrator(
    tmp_path: Path, session_id: str = "s948", **kwargs: Any
) -> ReviewPipelineOrchestrator:
    client = MagicMock()
    client._config = None
    return ReviewPipelineOrchestrator(
        session_id=session_id, target_dir=tmp_path, llm_client=client, **kwargs
    )


def test_findings_rank_by_status_before_severity_and_never_by_confidence() -> None:
    """Verify the order is reportable, then VERIFIED < UNVERIFIED < MITIGATED, then severity,
    location and title, and that a model's confidence plays no part: an UNVERIFIED finding at
    confidence 1.0 ranked above VERIFIED ones."""
    findings = [
        SavedFinding(
            title="Hallucinated advisory",
            location="src/z.py:1",
            severity="CRITICAL",
            confidence_score=1.0,
        ),
        SavedFinding(
            title="Mitigated escape",
            location="src/a.py:1",
            severity="CRITICAL",
            status="MITIGATED",
            mitigated=True,
            verified=True,
            verified_by="llm",
        ),
        _verified(title="Second at b", location="src/b.py:12", severity="MEDIUM"),
        _verified(
            title="First at b", location="src/b.py:9", severity="MEDIUM", confidence_score=0.1
        ),
        _verified(
            title="Real defect", location="src/c.py:3", severity="HIGH", confidence_score=0.5
        ),
        SavedFinding(
            title="Not reportable", location="src/a.py:1", severity="CRITICAL", reportable=False
        ),
    ]

    assert [f.title for f in sort_findings(findings)] == [
        "Real defect",
        "First at b",
        "Second at b",
        "Hallucinated advisory",
        "Mitigated escape",
        "Not reportable",
    ]


def test_an_unverified_advisory_never_reaches_the_headline(tmp_path: Path) -> None:
    """Verify the headline names defect classes of VERIFIED findings that recur, ranked by
    severity then count, and never a CVE, a finding title, or a class seen once."""
    findings = [
        SavedFinding(
            title="Log4Shell remote code execution in the pattern matcher",
            location="src/matcher.py:489",
            severity="CRITICAL",
            confidence_score=1.0,
            description="CVE-2021-44228 lets an attacker run code.",
            references=["CVE-2021-44228", "OWASP Top 10 A03: Injection"],
        ),
        _verified(
            title="Symlink lets list_files read outside the root",
            location="src/files.py:10",
            severity="HIGH",
            category="Path Traversal",
        ),
        _verified(
            title="Dot-dot segments escape the cache directory",
            location="src/cache.py:20",
            severity="MEDIUM",
            references=["CWE-22"],
        ),
        _verified(
            title="Sync loop never caps its retries",
            location="src/sync.py:7",
            severity="MEDIUM",
            category="Resource Exhaustion",
        ),
        _verified(
            title="Retry queue grows without a bound",
            location="src/queue.py:31",
            severity="LOW",
            category="Denial of Service",
        ),
        _verified(
            title="Broad except hides failed uploads",
            location="src/upload.py:5",
            severity="HIGH",
            category="Error Handling",
        ),
    ]
    report = _orchestrator(tmp_path)._build_consolidated_markdown_report(
        "s948", _NOW, sort_findings(findings), [], []
    )
    summary = _executive_summary(report)

    assert (
        "CVE-2021-44228" in summary,
        "Injection" in summary,
        "Error handling" in summary,
        [f.title for f in findings if f.title in summary],
        summary.index("Path traversal") < summary.index("Resource exhaustion"),
    ) == (False, False, False, [], True)


def test_counts_are_split_by_status_with_mitigated_apart(tmp_path: Path) -> None:
    """Verify the headline counts VERIFIED and UNVERIFIED findings apart, and lists the MITIGATED
    ones on their own, each with its severities."""
    findings = [
        _verified(title="Verified high", location="a.py:1", severity="HIGH"),
        _verified(title="Verified medium", location="b.py:1", severity="MEDIUM"),
        SavedFinding(title="Unverified low", location="c.py:1", severity="LOW"),
        SavedFinding(
            title="Mitigated critical",
            location="e.py:1",
            severity="CRITICAL",
            status="MITIGATED",
            mitigated=True,
            verified=True,
            verified_by="llm",
        ),
    ]
    summary = _executive_summary(
        _orchestrator(tmp_path)._build_consolidated_markdown_report("s948", _NOW, findings, [], [])
    )

    assert (
        "2 verified (1 High, 1 Medium)" in summary,
        "1 unverified (1 Low)" in summary,
        "1 mitigated (1 Critical)" in summary,
        "(1 Critical, 2 High" in summary,
    ) == (True, True, True, False)


@pytest.fixture
def scanners(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[list[Path]]]:
    """Bandit reports one CRITICAL, Gitleaks falls back to its built-in patterns and Semgrep
    fails; the paths each was handed are recorded."""
    seen: dict[str, list[list[Path]]] = {"Bandit": [], "Gitleaks": [], "Semgrep": []}
    critical = Finding(
        title="[B602] subprocess call with shell=True",
        location="app.py:1",
        severity="CRITICAL",
    )

    def scan(name: str, outcome: ScanOutcome) -> Any:
        def run(paths: list[Path], **_: Any) -> ScanOutcome:
            seen[name].append(list(paths))
            return outcome

        return run

    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan", scan("Bandit", ScanOutcome("ran", [critical]))
    )
    monkeypatch.setattr(
        "devops_cli.security.gitleaks.run_gitleaks_scan",
        scan("Gitleaks", ScanOutcome("built-in patterns", [])),
    )
    monkeypatch.setattr(
        "devops_cli.security.semgrep.run_semgrep_scan",
        scan("Semgrep", ScanOutcome("failed", [], reason="exit code 2")),
    )
    return seen


@pytest.mark.usefixtures("scanners")
def test_the_analyzer_line_comes_from_the_scan(tmp_path: Path) -> None:
    """Verify the executive summary counts an analyzer as run only when it ran, names the one on
    built-in patterns and the one that failed, and counts the scan's critical findings: one
    analyzer with a critical finding never yields "with 0 critical findings"."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    orchestrator = _orchestrator(tmp_path)
    orchestrator._run_static_scanners(["app.py"])

    summary = _executive_summary(
        orchestrator._build_consolidated_markdown_report("s948", _NOW, [], [], [])
    )

    assert (
        "0 critical findings" in summary,
        "**Static Security Analysis**: 1 analyzer(s) ran (Bandit). Static analyzers reported "
        "1 critical finding(s). Built-in patterns only: Gitleaks. Failed: Semgrep." in summary,
    ) == (False, True)


def test_the_terminal_summary_counts_by_status_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the terminal's Review Summary splits the reported findings by status as the report
    does, with the findings verification never reached and the MITIGATED ones apart."""
    tables: list[list[list[str]]] = []
    monkeypatch.setattr(
        "devops_cli.ai.review.pipeline.print_table", lambda **kw: tables.append(kw["rows"])
    )
    findings = [
        _verified(title="Verified high", location="a.py:1", severity="HIGH"),
        SavedFinding(title="Unverified low", location="c.py:1", severity="LOW"),
        SavedFinding(
            title="Mitigated critical",
            location="e.py:1",
            severity="CRITICAL",
            status="MITIGATED",
            mitigated=True,
            verified=True,
            verified_by="llm",
        ),
    ]
    _orchestrator(tmp_path)._render_console_summary_table(None, "s948", 3, findings, [], [])

    [rows] = tables
    assert dict(rows)["By Status"] == (
        "1 verified (1 High), 1 unverified (1 Low); listed apart: 1 mitigated (1 Critical)"
    )


def test_the_headline_names_the_first_three_recurring_classes(tmp_path: Path) -> None:
    """Verify the headline names the three most severe recurring classes and counts the rest,
    which Key Bad Patterns lists in full: the session's 20 recurring classes made a headline
    no one could read."""
    findings = [
        _verified(title=f"{word} defect {n}", location=f"src/{word}.py:{n}", severity=severity)
        for word, severity in (
            ("Injection", "HIGH"),
            ("Traversal", "HIGH"),
            ("SSRF", "MEDIUM"),
            ("Race", "LOW"),
        )
        for n in (1, 2)
    ]
    report = _orchestrator(tmp_path)._build_consolidated_markdown_report(
        "s948", _NOW, sort_findings(findings), [], []
    )
    headline = _executive_summary(report).split("\n\n", 1)[0]
    bad_patterns = report.split("### Key Bad Patterns Observed", 1)[1]

    assert (
        "which recur in Injection, Path traversal, SSRF and 1 more listed under Key Bad Patterns."
        in headline,
        "**Race condition**: 2 verified finding(s)" in bad_patterns,
    ) == (True, True)
