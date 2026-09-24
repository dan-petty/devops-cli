"""A static scan says which analyzers ran and which were not installed (#516).

A review printed "Static analyzers completed (0 finding(s) detected)" after naming six analyzers
when only Bandit was installed: Semgrep, Trivy, kube-linter and Pluto were skipped silently and
Gitleaks fell back to its built-in patterns. A reader took that for a clean scan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.review import pipeline
from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    _static_analyzer_states,
    _static_analyzer_summary,
)
from devops_cli.ai.review.profile import ReviewProfile, profiling, summarize_profiles
from devops_cli.commands import review as review_commands

_ONLY_BANDIT = {
    "Bandit": "ran",
    "Kube-linter": "not installed",
    "Pluto": "not installed",
    "Trivy": "not installed",
    "Semgrep": "not installed",
    "Gitleaks": "built-in patterns",
}


@pytest.fixture
def only_bandit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host where Bandit is the only analyzer installed, as in the reported review."""
    monkeypatch.setattr(pipeline, "check_binary", lambda binary: binary == "bandit")


@pytest.mark.usefixtures("only_bandit")
def test_each_analyzer_is_marked_ran_missing_fallback_or_without_files() -> None:
    """Verify every analyzer gets the state it actually had."""
    states = _static_analyzer_states(
        {"python": [Path("a.py")], "yaml": [], "container": [], "any": [Path("a.py")]}
    )

    assert states == {
        "Bandit": "ran",
        "Kube-linter": "no files",
        "Pluto": "no files",
        "Trivy": "no files",
        "Semgrep": "not installed",
        "Gitleaks": "built-in patterns",
    }


def test_the_summary_names_what_ran_and_what_was_not_installed() -> None:
    """Verify the console names the analyzers that ran and those that were skipped."""
    lines = _static_analyzer_summary(_ONLY_BANDIT, findings=0)

    assert lines == [
        "    [dim]✓ Static analyzers found 0 finding(s): Bandit, "
        "Gitleaks (built-in patterns) ran[/dim]",
        "    [yellow]! Not installed, so not run: Kube-linter, Pluto, Trivy, Semgrep[/yellow]",
    ]


def test_the_summary_says_when_no_analyzer_ran() -> None:
    """Verify a scan where nothing ran is not reported as completed."""
    lines = _static_analyzer_summary({"Bandit": "not installed", "Pluto": "no files"}, 0)

    assert lines == [
        "    [yellow]! No static analyzer ran[/yellow]",
        "    [yellow]! Not installed, so not run: Bandit[/yellow]",
    ]


@pytest.mark.usefixtures("only_bandit")
def test_a_review_with_only_bandit_is_not_reported_as_a_clean_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the reported case end to end: console, orchestrator state and review profile."""
    for name in ("app.py", "deploy.yaml", "Dockerfile"):
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr("devops_cli.security.bandit.run_bandit_scan", lambda paths: [])
    for scan in ("_scan_kubernetes_manifests", "_scan_container_and_lockfiles"):
        monkeypatch.setattr(pipeline, scan, lambda paths: [])
    monkeypatch.setattr(pipeline, "_scan_gitleaks_and_semgrep", lambda paths: [])
    printed: list[str] = []
    monkeypatch.setattr(pipeline, "print_info", lambda text, **_: printed.append(text))
    orchestrator = ReviewPipelineOrchestrator(session_id="s516", target_dir=tmp_path)

    with profiling() as profiler:
        orchestrator._run_static_scanners(["app.py", "deploy.yaml", "Dockerfile"])
    profile = profiler.build(session_id="s516", target=str(tmp_path))

    assert (orchestrator.static_analyzers, profile.static_analyzers) == (
        _ONLY_BANDIT,
        _ONLY_BANDIT,
    )
    assert printed[-1] == (
        "    [yellow]! Not installed, so not run: Kube-linter, Pluto, Trivy, Semgrep[/yellow]"
    )
    assert not any("completed" in line for line in printed)


def test_the_session_report_lists_each_analyzer_result(tmp_path: Path) -> None:
    """Verify the written report shows which analyzers ran."""
    orchestrator = ReviewPipelineOrchestrator(session_id="s516", target_dir=tmp_path)
    orchestrator.static_analyzers = _ONLY_BANDIT

    report = orchestrator._build_consolidated_markdown_report("s516", "now", [], [], [])

    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert section.splitlines() == [
        "| Analyzer | Result |",
        "|---|---|",
        "| Bandit | ran |",
        "| Kube-linter | not installed |",
        "| Pluto | not installed |",
        "| Trivy | not installed |",
        "| Semgrep | not installed |",
        "| Gitleaks | built-in patterns |",
    ]


def test_a_benchmark_tells_a_clean_scan_from_a_skipped_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify profiles keep the analyzer states and a benchmark shows each state seen."""
    first = ReviewProfile(session_id="a", target="t", static_analyzers=_ONLY_BANDIT)
    first.write(tmp_path)
    second = ReviewProfile(
        session_id="b", target="t", static_analyzers=_ONLY_BANDIT | {"Semgrep": "ran"}
    )
    printed: list[str] = []
    monkeypatch.setattr(review_commands, "print_info", lambda text, **_: printed.append(text))

    summary = summarize_profiles([ReviewProfile.load(tmp_path) or first, second])
    review_commands._render_benchmark(summary, tmp_path / "summary.json")

    assert (summary.static_analyzers["Semgrep"], summary.static_analyzers["Bandit"]) == (
        ["not installed", "ran"],
        ["ran"],
    )
    assert "Semgrep not installed / ran" in next(
        line for line in printed if line.startswith("Static analyzers: ")
    )
