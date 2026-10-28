"""A static scan says which analyzers ran and which were not installed (#516).

A review printed "Static analyzers completed (0 finding(s) detected)" after naming six analyzers
when only Bandit was installed: Semgrep, Trivy, kube-linter and Pluto were skipped silently and
Gitleaks fell back to its built-in patterns. A reader took that for a clean scan.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review import pipeline
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.pipeline import (
    ReviewPipelineOrchestrator,
    _compute_coverage_matrix,
    _resolve_effective_tool_states,
    _scan_kubernetes_manifests,
    _static_analyzer_states,
    _static_analyzer_summary,
)
from devops_cli.ai.review.profile import ReviewProfile, profiling, summarize_profiles
from devops_cli.ai.review_schema import Finding
from devops_cli.commands import review as review_commands
from devops_cli.config.constants import CONST_SANDBOX_TIMEOUT_EXIT_CODE
from devops_cli.review.session import ReviewSession
from devops_cli.security import is_kubernetes_manifest
from devops_cli.security.base import ScanOutcome
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.registry_cache import CACHED_RULESET_DIGEST, CACHED_RULESET_WORKDIR_NAME

# The report of a scan; no group analysis, so no model sees the admitted findings.
_NO_GROUP_ANALYSIS = ReviewStageFlags(group_analysis=False)

_ONLY_BANDIT = {
    "Bandit": "ran",
    "Kube-linter": "not installed",
    "Pluto": "not installed",
    "Trivy": "not installed",
    "Semgrep": "not installed",
    "Gitleaks": "not installed",
    "osv-scanner": "no files",
    "golangci-lint": "no files",
}


@pytest.fixture
def only_bandit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host where Bandit is the only analyzer installed, as in the reported review."""
    monkeypatch.setattr(pipeline, "check_binary", lambda binary: binary == "bandit")


@pytest.mark.usefixtures("only_bandit")
def test_each_analyzer_is_marked_ran_missing_fallback_or_without_files() -> None:
    """Verify every analyzer gets the state it actually had."""
    states = _static_analyzer_states(
        {
            "python": [Path("a.py")],
            "yaml": [],
            "container": [],
            "any": [Path("a.py")],
            "secrets": [Path("a.py")],
        }
    )

    assert states == {
        "Bandit": "ran",
        "Kube-linter": "no files",
        "Pluto": "no files",
        "Trivy": "no files",
        "Semgrep": "not installed",
        "Gitleaks": "not installed",
        "osv-scanner": "no files",
        "golangci-lint": "no files",
    }


def test_the_summary_names_what_ran_and_what_was_not_installed() -> None:
    """Verify the console names the analyzers that ran and those that were skipped."""
    lines = _static_analyzer_summary(_ONLY_BANDIT, findings=0)

    assert lines == [
        "    [dim]✓ Static analyzers found 0 finding(s): Bandit ran[/dim]",
        "    [yellow]! Not installed, so not run: Kube-linter, Pluto, Trivy, Semgrep, Gitleaks[/yellow]",
    ]


def test_the_summary_names_an_analyzer_with_a_coverage_gap_apart_from_those_that_ran() -> None:
    """Verify Semgrep is named when its scan ran and left files out (#1144). The console line
    did not name it, so the analyzer was missing from the line."""
    lines = _static_analyzer_summary({"Bandit": "ran", "Semgrep": "coverage_gap"}, findings=0)

    assert lines == [
        "    [dim]✓ Static analyzers found 0 finding(s): Bandit ran[/dim]",
        "    [yellow]! Coverage gap: Semgrep (the report's Static Analyzers table says why)[/yellow]",
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scanner_fake: ScannerFake,
) -> None:
    """Verify the reported case end to end: console, orchestrator state and review profile."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "deploy.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
    )
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    monkeypatch.setattr("devops_cli.security.bandit.run_bandit_scan", lambda paths, **_: [])
    for scan in ("_scan_kubernetes_manifests", "_scan_container_and_lockfiles"):
        monkeypatch.setattr(pipeline, scan, lambda paths: [])
    for scan in ("_scan_secrets", "_scan_semgrep"):
        monkeypatch.setattr(pipeline, scan, lambda paths, *_, **__: [])
    printed: list[str] = []
    monkeypatch.setattr(pipeline, "print_info", lambda text, **_: printed.append(text))
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s516", target_dir=tmp_path, tool_executor=scanner_fake
    )

    with profiling() as profiler:
        orchestrator._run_static_scanners(["app.py", "deploy.yaml", "Dockerfile"])
    profile = profiler.build(session_id="s516", target=str(tmp_path))

    assert (orchestrator.static_analyzers, profile.static_analyzers) == (
        _ONLY_BANDIT,
        _ONLY_BANDIT,
    )
    assert printed[-1] == (
        "    [yellow]! Not installed, so not run: Kube-linter, Pluto, Trivy, Semgrep, Gitleaks[/yellow]"
    )
    assert not any("completed" in line for line in printed)


def test_the_session_report_lists_each_analyzer_result(tmp_path: Path) -> None:
    """Verify the written report shows which analyzers ran."""
    orchestrator = ReviewPipelineOrchestrator(session_id="s516", target_dir=tmp_path)
    orchestrator.static_analyzers = _ONLY_BANDIT

    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert section.splitlines() == [
        "| Analyzer | Result |",
        "|---|---|",
        "| Bandit | ran |",
        "| Kube-linter | not installed |",
        "| Pluto | not installed |",
        "| Trivy | not installed |",
        "| Semgrep | not installed |",
        "| Gitleaks | not installed |",
        "| osv-scanner | no files |",
        "| golangci-lint | no files |",
    ]


def test_a_benchmark_tells_a_clean_scan_from_a_skipped_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify profiles keep the analyzer states and a benchmark shows each state seen."""
    first = ReviewProfile(session_id="a", target="t", static_analyzers=_ONLY_BANDIT)
    session = ReviewSession(tmp_path / "session")
    session.write_profile(first)
    second = ReviewProfile(
        session_id="b", target="t", static_analyzers=_ONLY_BANDIT | {"Semgrep": "ran"}
    )
    printed: list[str] = []
    monkeypatch.setattr(review_commands, "print_info", lambda text, **_: printed.append(text))

    summary = summarize_profiles([ReviewProfile.load(session.publish()) or first, second])
    review_commands._render_benchmark(summary, tmp_path / "summary.json")

    assert (summary.static_analyzers["Semgrep"], summary.static_analyzers["Bandit"]) == (
        ["not installed", "ran"],
        ["ran"],
    )
    assert "Semgrep not installed / ran" in next(
        line for line in printed if line.startswith("Static analyzers: ")
    )


@pytest.mark.usefixtures("only_bandit")
def test_the_report_says_why_an_analyzer_failed_and_the_console_points_there(
    tmp_path: Path,
) -> None:
    """Verify a failed analyzer's reason reaches its report row, escaped, and the console names it."""
    orchestrator = ReviewPipelineOrchestrator(session_id="s1009", target_dir=tmp_path)
    failed = ScanOutcome(
        "failed", [], 'Scanner exited with code 1; output was not JSON, starting "a | b"\nnext'
    )
    orchestrator._record_static_analyzers(
        {"python": [Path("a.py")], "yaml": [], "container": [], "any": [Path("a.py")]},
        observed_outcomes={"Bandit": failed},
    )

    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert (
        section.splitlines()[2],
        _static_analyzer_summary(orchestrator.static_analyzers, 0)[-1],
    ) == (
        "| Bandit | failed: Scanner exited with code 1; output was not JSON, starting "
        '"a \\| b" next |',
        "    [yellow]! Failed during execution: Bandit "
        "(the report's Static Analyzers table says why)[/yellow]",
    )


@pytest.mark.usefixtures("only_bandit")
def test_the_report_masks_a_secret_in_a_failed_analyzer_s_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scanner_fake: ScannerFake,
) -> None:
    """Verify a token a failing scanner printed instead of JSON never reaches review.md (#915)."""
    token = "ghp_" + "Q7rT2xW9yB4nM6kP1sD8fG3hJ5lZ0cV2aE7u"
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    scanner_fake.script(
        "bandit", ToolAnswer(exit_code=1, stdout=f"fatal: could not authenticate with {token}\n")
    )
    for scan in ("_scan_kubernetes_manifests", "_scan_container_and_lockfiles"):
        monkeypatch.setattr(pipeline, scan, lambda paths: [])
    for scan in ("_scan_secrets", "_scan_semgrep"):
        monkeypatch.setattr(pipeline, scan, lambda paths, *_, **__: [])
    monkeypatch.setattr(pipeline, "print_info", lambda text, **_: None)
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s915", target_dir=tmp_path, tool_executor=scanner_fake
    )

    orchestrator._run_static_scanners(["app.py"])
    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert (token in report, section.splitlines()[2]) == (
        False,
        "| Bandit | failed: Scanner exited with code 1; output was not JSON, starting "
        '"fatal: could not authenticate with <masked-github-token>" |',
    )


def test_a_scanner_timeout_reads_timed_out_in_the_report_and_the_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scanner_fake: ScannerFake,
) -> None:
    """Verify a scanner that ran out of time says so (#1079). Semgrep's row read `failed:
    Scanner execution failed: Command '['semgrep', 'scan', …`, cut before the timeout, and the
    profile said only `failed`. The profile also keeps how long each analyzer ran."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan", lambda *_, **__: ScanOutcome("ran")
    )
    for scan in ("_scan_kubernetes_manifests", "_scan_container_and_lockfiles", "_scan_secrets"):
        monkeypatch.setattr(pipeline, scan, lambda *_, **__: [])
    scanner_fake.script(
        "semgrep", ToolAnswer(exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE, timed_out=True)
    )
    monkeypatch.setattr(pipeline, "print_info", lambda text, **_: None)
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s1079", target_dir=tmp_path, tool_executor=scanner_fake
    )

    with profiling() as profiler:
        orchestrator._run_static_scanners(["app.py"])
    profile = profiler.build(session_id="s1079", target=str(tmp_path))
    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert (
        [row for row in section.splitlines() if row.startswith("| Semgrep ")],
        profile.static_analyzer_reasons,
        sorted(profile.static_analyzer_seconds),
    ) == (
        ["| Semgrep | failed: timed out after 300 s |"],
        {"Semgrep": "timed out after 300 s"},
        ["Semgrep"],
    )


def test_is_kubernetes_manifest_discrimination(tmp_path: Path) -> None:
    """Verify is_kubernetes_manifest distinguishes valid manifests from generic files (#1242)."""
    k8s_yaml = tmp_path / "valid.yaml"
    k8s_yaml.write_text(
        "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: test\n", encoding="utf-8"
    )
    k8s_json = tmp_path / "valid.json"
    k8s_json.write_text('{"apiVersion": "v1", "kind": "ConfigMap"}', encoding="utf-8")
    multi_doc = tmp_path / "multi.yaml"
    multi_doc.write_text(
        "---\ncomment: none\n---\napiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
    )
    labels_yaml = tmp_path / "labels.yml"
    labels_yaml.write_text("- name: bug\n  color: red\n", encoding="utf-8")
    workflow_yaml = tmp_path / "ci.yml"
    workflow_yaml.write_text("name: CI\non: push\njobs: {}\n", encoding="utf-8")
    python_file = tmp_path / "main.py"
    python_file.write_text('print("apiVersion = 1")\n', encoding="utf-8")
    nonexistent = tmp_path / "ghost.yaml"

    assert (
        is_kubernetes_manifest(k8s_yaml),
        is_kubernetes_manifest(k8s_json),
        is_kubernetes_manifest(multi_doc),
        is_kubernetes_manifest(labels_yaml),
        is_kubernetes_manifest(workflow_yaml),
        is_kubernetes_manifest(python_file),
        is_kubernetes_manifest(nonexistent),
    ) == (True, True, True, False, False, False, False)


def test_is_scannable_manifest_with_mocks_and_real_files(tmp_path: Path) -> None:
    """Verify _is_scannable_manifest discriminates real manifests and handles mocks (#1242)."""
    from devops_cli.ai.review.pipeline import _is_scannable_manifest

    manifest = tmp_path / "valid.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")
    non_manifest = tmp_path / "labels.yml"
    non_manifest.write_text("- name: bug\n", encoding="utf-8")
    ghost = tmp_path / "missing.yaml"

    assert (
        _is_scannable_manifest(manifest),
        _is_scannable_manifest(non_manifest),
        _is_scannable_manifest(ghost),
    ) == (True, False, False)

    with patch("devops_cli.security.kubelinter.run_kubelinter_scan", MagicMock()):
        assert _is_scannable_manifest(ghost) is True


def test_scan_kubernetes_manifests_skips_non_k8s_and_deleted_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify _scan_kubernetes_manifests executes only on real manifests (#1242)."""
    deleted_yaml = tmp_path / "deleted.yaml"
    labels_yaml = tmp_path / "labels.yml"
    labels_yaml.write_text("- name: bug\n", encoding="utf-8")
    manifest = tmp_path / "deploy.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

    scanned_kl: list[str] = []
    scanned_pl: list[str] = []

    def _mock_kl(path: Path, **_: Any) -> ScanOutcome:
        scanned_kl.append(path.name)
        return ScanOutcome("ran")

    def _mock_pl(path: Path, **_: Any) -> ScanOutcome:
        scanned_pl.append(path.name)
        return ScanOutcome("ran")

    monkeypatch.setattr("devops_cli.security.kubelinter.run_kubelinter_scan", _mock_kl)
    monkeypatch.setattr("devops_cli.security.pluto.run_pluto_scan", _mock_pl)

    outcomes: dict[str, Any] = {}
    findings = _scan_kubernetes_manifests([deleted_yaml, labels_yaml, manifest], outcomes=outcomes)

    assert (
        findings,
        scanned_kl,
        scanned_pl,
        outcomes["Kube-linter"].status,
        outcomes["Pluto"].status,
    ) == (
        [],
        ["deploy.yaml"],
        ["deploy.yaml"],
        "ran",
        "ran",
    )


def _static_scan(tmp_path: Path) -> tuple[ReviewPipelineOrchestrator, ReviewProfile]:
    """Run a review's static scanners over one Python file, under a profiler."""
    (tmp_path / "app.py").write_text('print("hello")\n', encoding="utf-8")
    orchestrator = ReviewPipelineOrchestrator(session_id="s1144", target_dir=tmp_path)
    with profiling() as profiler:
        orchestrator._run_static_scanners(["app.py"])
    return orchestrator, profiler.build(session_id="s1144", target=str(tmp_path))


def test_a_review_scans_with_the_cached_registry_ruleset_and_records_its_digest(
    scanner_fake: ScannerFake, cached_default_ruleset: Path, tmp_path: Path
) -> None:
    """The ruleset is an input of the review as the tools lock is: the profile keeps its digest
    (#1144)."""
    orchestrator, profile = _static_scan(tmp_path)

    (semgrep_run,) = (run for run in scanner_fake.runs if run.argv[0] == "semgrep")
    assert (
        orchestrator.static_analyzers["Semgrep"],
        profile.semgrep_registry_digest,
        semgrep_run.argv[semgrep_run.argv.index("--config") + 1],
    ) == ("ran", CACHED_RULESET_DIGEST, f"./{CACHED_RULESET_WORKDIR_NAME}")


def test_a_review_without_the_cached_ruleset_reports_a_coverage_gap_in_the_report_and_profile(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    reason = (
        "The registry rules p/default are not cached, or the cached file is not a Semgrep "
        "ruleset. Run `devops review rules fetch --ruleset p/default`."
    )

    orchestrator, profile = _static_scan(tmp_path)
    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]

    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert (
        [row for row in section.splitlines() if row.startswith("| Semgrep ")],
        profile.static_analyzers["Semgrep"],
        profile.static_analyzer_reasons["Semgrep"],
        profile.semgrep_registry_digest,
    ) == ([f"| Semgrep | coverage_gap: {reason} |"], "coverage_gap", reason, "")


def test_a_review_warns_when_the_cached_registry_ruleset_is_older_than_a_day_and_uses_it(
    scanner_fake: ScannerFake,
    cached_default_ruleset: Path,
    clock: ClockFake,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    aged = time.time() - 25 * 3600
    os.utime(cached_default_ruleset, (aged, aged))

    orchestrator, profile = _static_scan(tmp_path)

    assert (orchestrator.static_analyzers["Semgrep"], profile.semgrep_registry_digest) == (
        "ran",
        CACHED_RULESET_DIGEST,
    )
    assert (
        "! The cached registry rules p/default are 25 hours old, and the scan uses them. "
        "Run `devops review rules fetch --ruleset p/default` to refresh them.\n"
    ) in capsys.readouterr().out


def test_two_manifest_scan_where_one_fails_admits_good_findings_and_records_per_file_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed manifest gets failed(<reason>) in its row; the tool reads 'ran; N of M files failed' (#1140)."""
    good_yaml = tmp_path / "good.yaml"
    bad_yaml = tmp_path / "bad.yaml"
    good_yaml.write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: good\n", encoding="utf-8"
    )
    bad_yaml.write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: bad\n", encoding="utf-8"
    )

    good_finding = Finding(
        severity="HIGH",
        location=f"{good_yaml}:1",
        title="[privileged-container] Privileged container",
        description="Container runs as privileged",
        fix="Set securityContext.privileged to false",
        confidence_score=None,
    )

    def _mock_kl(path: Path, **_: Any) -> ScanOutcome:
        if path.name == "good.yaml":
            return ScanOutcome("ran", [good_finding])
        return ScanOutcome("failed", [], "Scanner execution failed: exit 1")

    monkeypatch.setattr("devops_cli.security.kubelinter.run_kubelinter_scan", _mock_kl)
    monkeypatch.setattr(
        "devops_cli.security.pluto.run_pluto_scan", lambda *_, **__: ScanOutcome("ran")
    )

    outcomes: dict[str, Any] = {}
    findings = _scan_kubernetes_manifests([good_yaml, bad_yaml], outcomes=outcomes)

    assert len(findings) == 1
    assert outcomes["Kube-linter"].status == "ran; 1 of 2 files failed"
    assert outcomes["Kube-linter"].reason == "Scanner execution failed: exit 1"

    orchestrator = ReviewPipelineOrchestrator(session_id="s1140", target_dir=tmp_path)
    orchestrator._record_static_analyzers(
        {"yaml": [good_yaml, bad_yaml], "python": [], "container": [], "any": []},
        observed_outcomes=outcomes,
    )

    assert orchestrator.static_analyzers["Kube-linter"] == "ran; 1 of 2 files failed"
    assert orchestrator.static_analyzer_reasons["Kube-linter"] == "Scanner execution failed: exit 1"

    report = orchestrator.generate_consolidated_report([], stage_flags=_NO_GROUP_ANALYSIS)[1]
    section = report.split("## Static Analyzers\n", 1)[1].split("\n\n", 1)[0]
    assert "| Kube-linter | ran; 1 of 2 files failed: Scanner execution failed: exit 1 |" in section

    tools = ["Kube-linter"]
    tool_effective_states = _resolve_effective_tool_states(
        orchestrator.static_analyzers,
        orchestrator.static_analyzer_reasons,
        orchestrator.static_analyzer_unscanned,
    )
    matrix = _compute_coverage_matrix(
        tools,
        ["good.yaml", "bad.yaml"],
        lambda f: tmp_path / f,
        tool_effective_states,
        {},
        unscanned=orchestrator.static_analyzer_unscanned,
        failed_files=orchestrator.static_analyzer_failed_files,
    )
    assert matrix["Kube-linter"]["good.yaml"] == "scanned"
    assert matrix["Kube-linter"]["bad.yaml"] == "failed(Scanner execution failed: exit 1)"


def test_manifest_scan_with_twenty_one_files_and_two_failures_records_fractional_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Status is recorded per file: 'ran; 2 of 21 files failed: <reason>' (#1140)."""
    manifests = [tmp_path / f"manifest_{i}.yaml" for i in range(21)]
    for m in manifests:
        m.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

    def _mock_kl(path: Path, **_: Any) -> ScanOutcome:
        if path.name in ("manifest_0.yaml", "manifest_1.yaml"):
            return ScanOutcome("failed", [], "Scanner execution failed: exit 1")
        return ScanOutcome("ran", [])

    monkeypatch.setattr("devops_cli.security.kubelinter.run_kubelinter_scan", _mock_kl)
    monkeypatch.setattr(
        "devops_cli.security.pluto.run_pluto_scan", lambda *_, **__: ScanOutcome("ran")
    )

    outcomes: dict[str, Any] = {}
    _scan_kubernetes_manifests(manifests, outcomes=outcomes)

    assert outcomes["Kube-linter"].status == "ran; 2 of 21 files failed"
    assert outcomes["Kube-linter"].reason == "Scanner execution failed: exit 1"
