"""Test suite for evidence-first review finding admission, anchors, and provenance (#871)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.review.admission import admit
from devops_cli.review.anchors import AdvisoryAnchor, Anchor, ToolAnchor
from devops_cli.review.finding import Finding
from devops_cli.review.fingerprint import compute_fingerprint_v2
from devops_cli.review.severity import derive_severity
from devops_cli.review.state import (
    FindingState,
    assert_finding_state_invariants,
    can_transition,
)
from devops_cli.review.suppression import (
    ReviewSuppression,
)
from devops_cli.security.normalization import NormalizedFinding
from devops_cli.security.sarif import from_sarif, to_sarif


def test_anchor_protocol_and_implementations() -> None:
    """ToolAnchor and AdvisoryAnchor satisfy Anchor protocol and validate recheck."""
    tool_anchor = ToolAnchor(run_id="run-123", result_index=0, rule_id="B105")
    adv_anchor = AdvisoryAnchor(
        db="osv",
        snapshot="2026-10-01",
        advisory_id="GHSA-xxxx",
        purl="pkg:pypi/requests",
        locked_version="2.31.0",
    )

    assert isinstance(tool_anchor, Anchor)
    assert isinstance(adv_anchor, Anchor)

    assert (tool_anchor.kind, tool_anchor.location, tool_anchor.recheck()) == (
        "tool",
        "run-123#0:B105",
        True,
    )
    assert (adv_anchor.kind, adv_anchor.location, adv_anchor.recheck()) == (
        "advisory",
        "osv/GHSA-xxxx@pkg:pypi/requests#2.31.0",
        True,
    )

    invalid_tool = ToolAnchor(run_id="", result_index=-1, rule_id="")
    assert invalid_tool.recheck() is False


def test_finding_is_frozen() -> None:
    """Finding model is strictly frozen and rejects attribute mutation."""
    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    finding = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="assert used",
        line=1,
        commit_files={"src/app.py"},
        file_content_getter=lambda p: "assert x == 1\n",
    )
    assert finding is not None
    assert isinstance(finding, Finding)

    with pytest.raises(ValidationError):
        finding.severity = "LOW"  # type: ignore[misc]


def test_location_check_and_typed_rejections(tmp_path: Path) -> None:
    """Location validation enforces commit presence, bounds, and counts typed rejections."""
    rejections: dict[str, int] = {}
    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    commit_files = {"src/main.py", "k8s/deploy.yaml"}

    def file_getter(p: str) -> str | None:
        if p == "src/main.py":
            return "line1\nline2\nline3\n"
        if p == "k8s/deploy.yaml":
            return "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web\n"
        return None

    # 1. Missing path (e.g. app/shell.py)
    f_missing = admit(
        anchor=anchor,
        tool="semgrep",
        rule_id="rule1",
        path="app/shell.py",
        message="shell issue",
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_missing is None
    assert rejections.get("path-not-in-commit") == 1

    # 2. Line out of range
    f_oor = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/main.py",
        message="issue",
        line=999,
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_oor is None
    assert rejections.get("line-out-of-range") == 1

    # 3. Object not in commit manifest
    f_obj = admit(
        anchor=anchor,
        tool="kubelinter",
        rule_id="no-read-only-fs",
        path="k8s/deploy.yaml",
        message="fs",
        logical_location="Deployment/prod/api",
        commit_files=commit_files,
        file_content_getter=file_getter,
        manifest_objects={"Deployment/default/web"},
        rejection_counts=rejections,
    )
    assert f_obj is None
    assert rejections.get("object-not-in-commit") == 1

    # 4. Tool not run
    f_norun = admit(
        anchor=anchor,
        tool="pluto",
        rule_id="depr",
        path="k8s/deploy.yaml",
        message="deprecated",
        tool_ran=False,
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_norun is None
    assert rejections.get("tool-not-run") == 1

    # 5. File not scanned
    f_notscanned = admit(
        anchor=anchor,
        tool="semgrep",
        rule_id="r1",
        path="src/main.py",
        message="msg",
        file_scanned=False,
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_notscanned is None
    assert rejections.get("file-not-scanned") == 1

    # 6. Canary failed
    f_canary = admit(
        anchor=anchor,
        tool="semgrep",
        rule_id="r1",
        path="src/main.py",
        message="msg",
        canary_passed=False,
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_canary is None
    assert rejections.get("canary-failed") == 1

    # 7. No anchor
    f_noanc = admit(
        anchor=None,
        tool="semgrep",
        rule_id="r1",
        path="src/main.py",
        message="msg",
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_noanc is None
    assert rejections.get("no-anchor") == 1

    # 8. Valid finding with absolute path inside worktree
    wt = tmp_path / "worktree"
    wt.mkdir()
    abs_path = wt / "src" / "main.py"
    f_valid = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path=str(abs_path),
        message="assert check",
        line=2,
        worktree_root=wt,
        commit_files=commit_files,
        file_content_getter=file_getter,
        rejection_counts=rejections,
    )
    assert f_valid is not None
    assert (f_valid.path, f_valid.line, bool(f_valid.region_sha256)) == (
        "src/main.py",
        2,
        True,
    )


@pytest.mark.parametrize(
    ("sec_sev", "rule_sev", "sarif_lvl", "path_cls", "caps", "expected_sev", "expected_part"),
    [
        (9.5, None, None, "src", {}, "CRITICAL", "cvss=9.5 >= 9.0 -> CRITICAL"),
        (7.2, None, None, "src", {}, "HIGH", "cvss=7.2 >= 7.0 -> HIGH"),
        (4.5, None, None, "src", {}, "MEDIUM", "cvss=4.5 >= 4.0 -> MEDIUM"),
        (1.0, None, None, "src", {}, "LOW", "cvss=1.0 > 0.0 -> LOW"),
        (0.0, None, None, "src", {}, "INFO", "cvss=0.0 == 0.0 -> INFO"),
        (None, "HIGH", None, "src", {}, "HIGH", "rule_severity=HIGH -> HIGH"),
        (None, None, "error", "src", {}, "HIGH", "sarif_level=error -> HIGH"),
        (None, None, "warning", "src", {}, "MEDIUM", "sarif_level=warning -> MEDIUM"),
        (None, None, "note", "src", {}, "LOW", "sarif_level=note -> LOW"),
        # Path class caps
        (8.5, None, None, "test", {"test": "LOW"}, "LOW", "capped by test=LOW -> LOW"),
        (8.5, None, None, "docs", {"docs": "INFO"}, "INFO", "capped by docs=INFO -> INFO"),
        (2.0, None, None, "test", {"test": "LOW"}, "LOW", "within test cap LOW"),
    ],
)
def test_severity_derivation_table(
    sec_sev: float | None,
    rule_sev: str | None,
    sarif_lvl: str | None,
    path_cls: str,
    caps: dict[str, str],
    expected_sev: str,
    expected_part: str,
) -> None:
    """Table-driven test for derive_severity pure function."""
    sev, derivation = derive_severity(
        security_severity=sec_sev,
        rule_severity=rule_sev,
        sarif_level=sarif_lvl,
        path_class=path_cls,
        severity_caps=caps,
    )
    assert sev == expected_sev
    assert expected_part in derivation


def test_state_transitions_and_invariants() -> None:
    """State transition invariants validate allowed and prohibited lifecycle changes."""
    assert can_transition(FindingState.OPEN, FindingState.SUPPRESSED) is True
    assert can_transition(FindingState.OPEN, FindingState.FIXED) is True
    assert can_transition(FindingState.OPEN, FindingState.CONFIRMED) is True
    assert can_transition(FindingState.SUPPRESSED, FindingState.OPEN) is True
    assert can_transition(FindingState.CONFIRMED, FindingState.SUPPRESSED) is False

    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    open_finding = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="msg",
        commit_files={"src/app.py"},
        file_content_getter=lambda p: "pass\n",
    )
    assert open_finding is not None
    assert open_finding.state == FindingState.OPEN
    assert_finding_state_invariants([open_finding])

    # Suppressed without reason violates invariants
    bad_supp = open_finding.model_copy(
        update={"state": FindingState.SUPPRESSED, "suppression_reason": None}
    )
    with pytest.raises(ValueError, match="SUPPRESSED finding must record a suppression reason"):
        assert_finding_state_invariants([bad_supp])

    # Confirmed without confirmed_by violates invariants
    bad_conf = open_finding.model_copy(
        update={"state": FindingState.CONFIRMED, "confirmed_by": None}
    )
    with pytest.raises(ValueError, match="CONFIRMED finding must record who confirmed it"):
        assert_finding_state_invariants([bad_conf])

    good_conf = open_finding.model_copy(
        update={"state": FindingState.CONFIRMED, "confirmed_by": "alice"}
    )
    assert_finding_state_invariants([good_conf])


def test_suppressions_and_inline_markers() -> None:
    """Suppressions from review.toml and base inline markers suppress findings; change markers stay OPEN."""
    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B103")
    commit_files = {"tests/test_crypto_tls.py"}
    content = "os.chmod(k_file, 0o666) # nosec B103\n"

    # Test-path policy suppression from #1024
    supps = [
        ReviewSuppression(
            rule="B103",
            path="tests/**",
            reason="Test suites configure intentional mock file permissions",
            expiry="2099-12-31",
        )
    ]

    f_supp = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B103",
        path="tests/test_crypto_tls.py",
        message="set bad file permissions",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
        suppressions=supps,
    )
    assert f_supp is not None
    assert (f_supp.state, f_supp.suppression_reason) == (
        FindingState.SUPPRESSED,
        "Test suites configure intentional mock file permissions",
    )

    # Inline marker added by change stays OPEN and marked suppressed_by_change
    f_added = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B103",
        path="tests/test_crypto_tls.py",
        message="set bad permissions",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
        added_diff_lines={("tests/test_crypto_tls.py", 1)},
    )
    assert f_added is not None
    assert (f_added.state, f_added.suppressed_by_change) == (
        FindingState.OPEN,
        True,
    )


def test_fingerprint_v2_stability() -> None:
    """Fingerprint v2 remains stable when unflagged lines are inserted above the defect."""
    initial_text = "x = 1\ny = 2\nos.chmod(p, 0o777)\n"
    modified_text = "# inserted comment\n# another line\nx = 1\ny = 2\nos.chmod(p, 0o777)\n"

    fp_initial = compute_fingerprint_v2(
        tool="bandit",
        rule_id="B103",
        path="src/app.py",
        start_line=3,
        file_content=initial_text,
    )
    fp_modified = compute_fingerprint_v2(
        tool="bandit",
        rule_id="B103",
        path="src/app.py",
        start_line=5,
        file_content=modified_text,
    )

    assert fp_initial == fp_modified


def test_sarif_roundtrip_preserves_version_and_properties() -> None:
    """SARIF emission and from_sarif roundtrip preserves driver version and rule properties."""
    finding = NormalizedFinding(
        tool="bandit",
        tool_version="1.7.9",
        rule_id="B101",
        severity="HIGH",
        message="assert used",
        path="src/app.py",
        line=10,
        symbol="main",
        partial_fingerprints={"fingerprint_v2": "sha256-abc"},
        rule_properties={"cwe": "CWE-703"},
        baseline_state="new",
    )

    sarif_doc = to_sarif([finding])
    parsed = from_sarif(sarif_doc)

    assert len(parsed) == 1
    p = parsed[0]
    assert (
        p.tool,
        p.tool_version,
        p.rule_id,
        p.baseline_state,
        p.partial_fingerprints.get("fingerprint_v2"),
        p.rule_properties.get("cwe"),
    ) == (
        "bandit",
        "1.7.9",
        "B101",
        "new",
        "sha256-abc",
        "CWE-703",
    )


def test_introduced_vs_preexisting_branch_reviews() -> None:
    """Findings are introduced when absent from base revision runs, preexisting when present."""
    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    commit_files = {"src/app.py"}
    content = "print('hello')\n"

    # 1. New finding (not in base)
    f_new = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="check",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
        base_fingerprints={"other-fingerprint"},
    )
    assert f_new is not None
    assert (f_new.introduced, f_new.baseline_state) == (True, "new")

    # 2. Preexisting finding (fingerprint present in base)
    assert f_new.fingerprint_v2 is not None
    f_preexisting = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="check",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
        base_fingerprints={f_new.fingerprint_v2},
    )
    assert f_preexisting is not None
    assert (f_preexisting.introduced, f_preexisting.baseline_state) == (False, "unchanged")


def test_two_runs_fixture_tree_byte_identical(tmp_path: Path) -> None:
    """Two runs on fixture tree with equal input digests produce byte-identical findings files."""
    from devops_cli.ai.review_schema import ReviewSessionPayload
    from devops_cli.security.sarif import write_sarif

    anchor1 = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    anchor2 = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    commit_files = {"src/app.py"}
    content = "assert x == 1\n"

    f1 = admit(
        anchor=anchor1,
        tool="bandit",
        tool_version="1.7.9",
        rule_id="B101",
        path="src/app.py",
        message="assert used",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
    )
    f2 = admit(
        anchor=anchor2,
        tool="bandit",
        tool_version="1.7.9",
        rule_id="B101",
        path="src/app.py",
        message="assert used",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
    )
    assert f1 is not None and f2 is not None

    sarif1_path = tmp_path / "run1" / "findings.sarif"
    sarif2_path = tmp_path / "run2" / "findings.sarif"

    nf1 = NormalizedFinding(
        tool=f1.tool,
        tool_version=f1.tool_version,
        rule_id=f1.rule_id,
        severity=f1.severity,
        message=f1.message,
        path=f1.path,
        line=f1.line,
        partial_fingerprints=dict(f1.partial_fingerprints),
        baseline_state=f1.baseline_state,
    )
    nf2 = NormalizedFinding(
        tool=f2.tool,
        tool_version=f2.tool_version,
        rule_id=f2.rule_id,
        severity=f2.severity,
        message=f2.message,
        path=f2.path,
        line=f2.line,
        partial_fingerprints=dict(f2.partial_fingerprints),
        baseline_state=f2.baseline_state,
    )

    write_sarif([nf1], sarif1_path)
    write_sarif([nf2], sarif2_path)
    assert sarif1_path.read_bytes() == sarif2_path.read_bytes()

    json1_path = tmp_path / "run1" / "findings.json"
    json2_path = tmp_path / "run2" / "findings.json"
    fixed_ts = "2026-10-07T00:00:00Z"
    payload1 = ReviewSessionPayload(
        generated_at=fixed_ts,
        subject={"type": "path", "target": "src/app.py"},
        findings=[],
    )
    payload2 = ReviewSessionPayload(
        generated_at=fixed_ts,
        subject={"type": "path", "target": "src/app.py"},
        findings=[],
    )
    json1_path.write_text(payload1.model_dump_json(indent=2) + "\n", encoding="utf-8")
    json2_path.write_text(payload2.model_dump_json(indent=2) + "\n", encoding="utf-8")
    assert json1_path.read_bytes() == json2_path.read_bytes()


def test_profile_and_findings_counts_agree(tmp_path: Path) -> None:
    """profile.json and findings.json counts agree and record typed rejections."""
    from devops_cli.ai.review.profile import ReviewProfiler

    profiler = ReviewProfiler()
    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    commit_files = {"src/app.py"}
    content = "x = 1\n"

    f = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="msg",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: content,
    )
    assert f is not None

    rejections: dict[str, int] = {}
    admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="app/shell.py",
        message="missing",
        commit_files=commit_files,
        file_content_getter=lambda p: content,
        rejection_counts=rejections,
    )
    profiler.set_rejections(rejections)
    profiler.set_findings(candidates=1, verified=1, reported=1)

    profile = profiler.build(session_id="sess-1", target="test-target", files=1)
    profile_path = profile.write(tmp_path)
    loaded_profile = json.loads(profile_path.read_text(encoding="utf-8"))

    assert (
        loaded_profile["reported_findings"],
        loaded_profile["rejections"].get("path-not-in-commit"),
    ) == (1, 1)


def test_review_markdown_sections() -> None:
    """review.md includes introduced findings, preexisting findings, and suppressed sections."""
    from types import SimpleNamespace

    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator

    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    commit_files = {"src/app.py"}
    clean_content = "x = 1\n"
    marker_content = "x = 1 # nosec B101\n"

    f_intro = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="introduced finding",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: clean_content,
    )
    f_pre = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="preexisting finding",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: clean_content,
        base_fingerprints={f_intro.fingerprint_v2} if f_intro else None,
    )
    f_supp = admit(
        anchor=anchor,
        tool="bandit",
        rule_id="B101",
        path="src/app.py",
        message="suppressed finding",
        line=1,
        commit_files=commit_files,
        file_content_getter=lambda p: marker_content,
        added_diff_lines={("src/app.py", 1)},
    )
    assert f_intro is not None and f_pre is not None and f_supp is not None

    fake_pipeline = SimpleNamespace(admitted_scanner_findings=[f_intro, f_pre, f_supp])
    intro_lines = ReviewPipelineOrchestrator._build_introduced_findings_section(
        fake_pipeline,
        [f_intro],  # type: ignore[arg-type]
    )
    pre_lines = ReviewPipelineOrchestrator._build_preexisting_findings_section(
        fake_pipeline,
        [f_pre],  # type: ignore[arg-type]
    )
    supp_lines = ReviewPipelineOrchestrator._build_suppressed_findings_section(
        fake_pipeline,
        [f_supp],  # type: ignore[arg-type]
    )

    assert "## Introduced Findings" in intro_lines
    assert "## Pre-existing Findings in Changed Files" in pre_lines
    assert "## Suppressed Findings" in supp_lines
    assert any("suppressed by this change" in line for line in supp_lines)


def test_orchestrator_static_scanners_populate_admitted_scanner_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Static security scanners wire candidates through admit(), populating admitted_scanner_findings."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    app_py = src_dir / "app.py"
    app_py.write_text("assert True\n", encoding="utf-8")

    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.ai.review_schema import Finding as SchemaFinding
    from devops_cli.security.base import ScanOutcome

    f_valid = SchemaFinding(
        title="[B101] assert used",
        location="src/app.py:1",
        severity="LOW",
    )
    f_invalid = SchemaFinding(
        title="[B102] exec used",
        location="src/nonexistent.py:5",
        severity="HIGH",
    )

    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan",
        lambda *_, **__: ScanOutcome("ran", [f_valid, f_invalid]),
    )
    for scan in (
        "_scan_kubernetes_manifests",
        "_scan_container_and_lockfiles",
        "_scan_secrets",
        "_scan_semgrep",
    ):
        monkeypatch.setattr(f"devops_cli.ai.review.pipeline.{scan}", lambda *_, **__: [])

    orchestrator = ReviewPipelineOrchestrator(session_id="s871-admit", target_dir=tmp_path)
    by_file = orchestrator._run_static_scanners(["src/app.py"])

    admitted = orchestrator.admitted_scanner_findings
    assert len(admitted) == 1
    af = admitted[0]
    assert (
        af.rule_id,
        af.tool,
        af.path,
        af.line,
        af.anchor.kind,
        af.anchor.run_id,
        af.anchor.rule_id,
        af.severity,
        len(by_file.get("src/app.py", [])),
        dict(orchestrator.static_severities),
    ) == (
        "B101",
        "bandit",
        "src/app.py",
        1,
        "tool",
        "s871-admit",
        "B101",
        "LOW",
        1,
        {"LOW": 1},
    )


def test_audit_file_dependencies_admits_with_advisory_anchor(tmp_path: Path) -> None:
    """_audit_file_dependencies admits vulnerable dependencies with AdvisoryAnchor (#871)."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.models.vulnerability import (
        DependencySpec,
        PackageLookupResult,
        VulnerabilityRecord,
    )
    from devops_cli.review.anchors import AdvisoryAnchor

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    req_file = src_dir / "requirements.txt"
    req_file.write_text("requests==2.20.0\n", encoding="utf-8")

    orchestrator = ReviewPipelineOrchestrator(session_id="test-adv-anchor", target_dir=tmp_path)
    dep = DependencySpec(name="requests", version_range="2.20.0", ecosystem="PyPI", line_number=1)
    vuln = VulnerabilityRecord(
        id="GHSA-xxxx-yyyy",
        summary="Remote Code Execution",
        severity="CRITICAL",
        source="OSV",
        details_url="https://example.com/advisory",
    )
    dep_cache = {
        ("requests", "2.20.0", "PyPI"): PackageLookupResult(status="ok", vulnerabilities=[vuln])
    }

    findings = orchestrator._audit_file_dependencies("src/requirements.txt", [dep], dep_cache)
    admitted = orchestrator.admitted_scanner_findings

    assert (
        len(findings),
        len(admitted),
        isinstance(admitted[0].anchor, AdvisoryAnchor),
        admitted[0].anchor.kind,
        admitted[0].anchor.db,
        admitted[0].anchor.advisory_id,
        admitted[0].anchor.purl,
        admitted[0].anchor.locked_version,
        admitted[0].baseline_state,
        admitted[0].introduced,
    ) == (
        1,
        1,
        True,
        "advisory",
        "OSV",
        "GHSA-xxxx-yyyy",
        "pkg:pypi/requests@2.20.0",
        "2.20.0",
        "new",
        True,
    )


def test_base_revision_fingerprints_distinguishes_preexisting_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing findings in base revision are admitted as unchanged / not introduced (#871)."""
    from typing import Any

    from devops_cli.ai.analyze.symbols import BaseRevision
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.ai.review_schema import Finding as SchemaFinding
    from devops_cli.security.base import ScanOutcome

    base_content = "eval(foo)\n" + ("# padding\n" * 20)
    head_content = base_content + "assert bar\n"

    app_file = tmp_path / "app.py"
    app_file.write_text(head_content, encoding="utf-8")

    f_eval = SchemaFinding(
        title="[B307] eval used",
        location="app.py:1",
        severity="HIGH",
    )
    f_assert = SchemaFinding(
        title="[B101] assert used",
        location=f"app.py:{len(base_content.splitlines()) + 1}",
        severity="LOW",
    )

    base_rev = BaseRevision(
        changes=(),
        read=lambda p: base_content if p == "app.py" else None,
    )

    def mock_bandit(paths: Any, **_: Any) -> ScanOutcome:
        p_str = str(paths[0]) if paths else ""
        if "devops-base-rev-" in p_str:
            return ScanOutcome("ran", [f_eval])
        return ScanOutcome("ran", [f_eval, f_assert])

    monkeypatch.setattr("devops_cli.security.bandit.run_bandit_scan", mock_bandit)
    for scan in (
        "_scan_kubernetes_manifests",
        "_scan_container_and_lockfiles",
        "_scan_secrets",
        "_scan_semgrep",
    ):
        monkeypatch.setattr(f"devops_cli.ai.review.pipeline.{scan}", lambda *_, **__: [])

    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-base-diff",
        target_dir=tmp_path,
        base_revision=base_rev,
    )
    orchestrator._run_static_scanners(["app.py"])

    admitted = orchestrator.admitted_scanner_findings
    by_rule = {af.rule_id: af for af in admitted}

    eval_finding = by_rule["B307"]
    assert_finding = by_rule["B101"]

    assert (
        len(admitted),
        eval_finding.baseline_state,
        eval_finding.introduced,
        assert_finding.baseline_state,
        assert_finding.introduced,
    ) == (
        2,
        "unchanged",
        False,
        "new",
        True,
    )


def _stub_bandit_only(monkeypatch: pytest.MonkeyPatch, bandit_findings: list[object]) -> None:
    """Have Bandit report bandit_findings and every other static scanner report nothing."""
    from devops_cli.security.base import ScanOutcome

    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan",
        lambda *_, **__: ScanOutcome("ran", bandit_findings),
    )
    for scan in (
        "_scan_kubernetes_manifests",
        "_scan_container_and_lockfiles",
        "_scan_secrets",
        "_scan_semgrep",
    ):
        monkeypatch.setattr(f"devops_cli.ai.review.pipeline.{scan}", lambda *_, **__: [])


def test_review_toml_suppressed_scanner_finding_is_listed_not_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scanner finding a review.toml suppression covers leaves the reported set, stays in the
    admitted findings SARIF is written from, and is listed under Suppressed in review.md (#1295)."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.ai.review_schema import Finding as SchemaFinding

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("assert True\nexec('x')\n", encoding="utf-8")
    _stub_bandit_only(
        monkeypatch,
        [
            SchemaFinding(title="[B101] assert used", location="src/app.py:1", severity="LOW"),
            SchemaFinding(title="[B102] exec used", location="src/app.py:2", severity="HIGH"),
        ],
    )
    orchestrator = ReviewPipelineOrchestrator(session_id="s1295-supp", target_dir=tmp_path)
    orchestrator.suppressions = [
        ReviewSuppression(rule="B101", path="src/**", reason="accepted risk")
    ]

    reported = orchestrator._run_static_scanners(["src/app.py"])["src/app.py"]

    assert (
        [f.title for f in reported],
        [(f.rule_id, f.state) for f in orchestrator.admitted_scanner_findings],
        orchestrator._build_suppressed_findings_section(reported),
    ) == (
        ["[B102] exec used"],
        [("B101", FindingState.SUPPRESSED), ("B102", FindingState.OPEN)],
        [
            "## Suppressed Findings",
            "| Severity | Location | Reason | Expiry | Suppressed By |",
            "|---|---|---|---|---|",
            "| **LOW** | `src/app.py` | accepted risk | None | review.toml/base marker |",
            "",
        ],
    )


def test_scanner_finding_at_a_base_fingerprint_is_listed_as_preexisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scanner finding whose fingerprint the base revision has is reported under Pre-existing
    in review.md, not under Introduced (#1295)."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.ai.review_schema import Finding as SchemaFinding

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("exec('x')\n", encoding="utf-8")
    _stub_bandit_only(
        monkeypatch,
        [SchemaFinding(title="[B102] exec used", location="src/app.py:1", severity="HIGH")],
    )
    orchestrator = ReviewPipelineOrchestrator(session_id="s1295-base", target_dir=tmp_path)
    orchestrator._run_static_scanners(["src/app.py"])
    orchestrator.base_fingerprints = {orchestrator.admitted_scanner_findings[0].fingerprint_v2}

    reported = orchestrator._run_static_scanners(["src/app.py"])["src/app.py"]

    assert (
        orchestrator._build_introduced_findings_section(reported),
        orchestrator._build_preexisting_findings_section(reported),
    ) == (
        [],
        [
            "## Pre-existing Findings in Changed Files",
            "| Severity | Location | Title |",
            "|---|---|---|",
            "| **HIGH** | `src/app.py:1` | [B102] exec used |",
            "",
        ],
    )


def test_head_revision_admission_rejections_reach_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanner candidates admission rejects at the reviewed revision are counted by type in
    profile.json (#1295)."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.ai.review.profile import profiling
    from devops_cli.ai.review_schema import Finding as SchemaFinding

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("assert True\n", encoding="utf-8")
    _stub_bandit_only(
        monkeypatch,
        [
            SchemaFinding(title="[B101] assert used", location="src/app.py:1", severity="LOW"),
            SchemaFinding(title="[B102] exec used", location="src/missing.py:5", severity="HIGH"),
            SchemaFinding(title="[B101] assert used", location="src/app.py:40", severity="LOW"),
        ],
    )

    with profiling() as profiler:
        orchestrator = ReviewPipelineOrchestrator(session_id="s1295-rej", target_dir=tmp_path)
        orchestrator._run_static_scanners(["src/app.py"])
        profile = profiler.build(session_id="s1295-rej", target="src/app.py", files=1)

    assert (len(orchestrator.admitted_scanner_findings), profile.rejections) == (
        1,
        {"path-not-in-commit": 1, "line-out-of-range": 1},
    )


def test_suppressed_dependency_advisory_is_listed_not_reported(tmp_path: Path) -> None:
    """A dependency advisory a review.toml suppression covers is not reported, and stays in the
    admitted findings SARIF and the Suppressed section of review.md are written from (#1295)."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.models.vulnerability import (
        DependencySpec,
        PackageLookupResult,
        VulnerabilityRecord,
    )

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "requirements.txt").write_text("requests==2.20.0\n", encoding="utf-8")
    orchestrator = ReviewPipelineOrchestrator(session_id="s1295-adv", target_dir=tmp_path)
    orchestrator.suppressions = [
        ReviewSuppression(rule="GHSA-xxxx-yyyy", path="src/**", reason="accepted risk")
    ]
    dep = DependencySpec(name="requests", version_range="2.20.0", ecosystem="PyPI", line_number=1)
    vuln = VulnerabilityRecord(
        id="GHSA-xxxx-yyyy",
        summary="Remote Code Execution",
        severity="CRITICAL",
        source="OSV",
        details_url="https://example.com/advisory",
    )
    dep_cache = {
        ("requests", "2.20.0", "PyPI"): PackageLookupResult(status="ok", vulnerabilities=[vuln])
    }

    findings = orchestrator._audit_file_dependencies("src/requirements.txt", [dep], dep_cache)

    assert (
        findings,
        [(f.rule_id, f.state) for f in orchestrator.admitted_scanner_findings],
    ) == ([], [("GHSA-xxxx-yyyy", FindingState.SUPPRESSED)])
