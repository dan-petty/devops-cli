"""Unit tests for security tools integration in AI review pipeline and native agent tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import Finding
from devops_cli.ai.tools.builtin_tools import (
    scan_bandit,
    scan_kubelinter,
    scan_pluto,
    scan_popeye,
    scan_trivy,
)
from devops_cli.ai.tools.registry import get_default_tools


def test_native_security_tools_in_registry() -> None:
    """get_default_tools must register all discrete security scanner tools."""
    tools = get_default_tools()
    tool_names = [t.__name__ for t in tools if hasattr(t, "__name__")]
    assert "scan_trivy" in tool_names
    assert "scan_kubelinter" in tool_names
    assert "scan_pluto" in tool_names
    assert "scan_bandit" in tool_names
    assert "scan_popeye" in tool_names


@patch("devops_cli.ai.tools.builtin_tools._run_tool_cmd")
def test_native_security_tool_invocations(mock_cmd: MagicMock, tmp_path: Path) -> None:
    """Security tools must execute safe subprocess commands."""
    mock_cmd.return_value = "No security issues detected."

    res_trivy = scan_trivy("src")
    assert res_trivy == "No security issues detected."
    assert mock_cmd.call_count == 1

    res_kl = scan_kubelinter("k8s")
    assert res_kl == "No security issues detected."

    res_pluto = scan_pluto("k8s")
    assert res_pluto == "No security issues detected."

    res_bandit = scan_bandit("src")
    assert res_bandit == "No security issues detected."

    res_popeye = scan_popeye(namespace="monitoring")
    assert res_popeye == "No security issues detected."


@patch("devops_cli.security.trivy.run_trivy_scan")
@patch("devops_cli.security.kubelinter.run_kubelinter_scan")
@patch("devops_cli.security.pluto.run_pluto_scan")
@patch("devops_cli.security.bandit.run_bandit_scan")
def test_pipeline_multi_scanner_aggregation(
    mock_bandit: MagicMock,
    mock_pluto: MagicMock,
    mock_kl: MagicMock,
    mock_trivy: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify payloads aggregate findings across Trivy, Kube-linter, Pluto, Bandit."""
    mock_trivy.return_value = [
        Finding(
            severity="CRITICAL",
            location="Dockerfile:cve-1",
            title="[CVE-2026-1001] OpenSSL Vulnerability",
            description="Buffer overflow in crypto",
            fix="Upgrade OpenSSL",
            confidence_score=0.95,
        )
    ]
    mock_bandit.return_value = [
        Finding(
            severity="HIGH",
            location="src/main.py:10",
            title="[B602] Shell injection",
            description="Subprocess shell=True",
            fix="Use list args",
            confidence_score=0.95,
        )
    ]
    mock_kl.return_value = [
        Finding(
            severity="MEDIUM",
            location="k8s/app.yaml:Deployment/app",
            title="[no-read-only-root-fs] Root filesystem writeable",
            description="Set readOnlyRootFilesystem to true",
            fix="Update securityContext",
            confidence_score=0.9,
        )
    ]
    mock_pluto.return_value = [
        Finding(
            severity="HIGH",
            location="k8s/app.yaml:Ingress/app",
            title="[Removed API] Ingress uses extensions/v1beta1",
            description="Deprecated in 1.22",
            fix="Upgrade to networking.k8s.io/v1",
            confidence_score=0.95,
        )
    ]

    (tmp_path / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.py").write_text("import os\n" * 15, encoding="utf-8")
    k8s_dir = tmp_path / "k8s"
    k8s_dir.mkdir(parents=True, exist_ok=True)
    (k8s_dir / "app.yaml").write_text("apiVersion: v1\n", encoding="utf-8")

    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-sec-tools",
        session_dir=tmp_path / "test-sec-tools",
        target_dir=tmp_path,
    )
    payloads = orchestrator.init_per_file_payloads(
        file_paths=["Dockerfile", "src/main.py", "k8s/app.yaml"],
        metadata_by_path={},
    )

    assert len(payloads) == 3
    docker_payload = next(p for p in payloads if p.file_path == "Dockerfile")
    py_payload = next(p for p in payloads if p.file_path == "src/main.py")
    yaml_payload = next(p for p in payloads if p.file_path == "k8s/app.yaml")

    # Docker payload has Trivy
    docker_titles = [f.title for f in docker_payload.findings]
    assert any("CVE-2026-1001" in t for t in docker_titles)

    # Python payload has Bandit
    py_titles = [f.title for f in py_payload.findings]
    assert any("B602" in t for t in py_titles)

    # YAML payload has Kube-linter + Pluto
    yaml_titles = [f.title for f in yaml_payload.findings]
    assert any("no-read-only-root-fs" in t for t in yaml_titles)
    assert any("Removed API" in t for t in yaml_titles)


@patch("devops_cli.security.bandit.run_bandit_scan")
def test_review_pipeline_admit_inline_suppression_added_by_change(
    mock_bandit: MagicMock,
    tmp_path: Path,
) -> None:
    """Inline suppressions added by the change stay OPEN with suppressed_by_change=True."""
    from devops_cli.review.state import FindingState

    mock_bandit.return_value = [
        Finding(
            severity="HIGH",
            location="src/main.py:1",
            title="[B602] Shell injection",
            description="Subprocess shell=True",
            fix="Use list args",
            confidence_score=0.95,
        )
    ]
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    # Bandit's own marker: Bandit ignores `# noqa`, and so does admission (#1341)
    (src_dir / "main.py").write_text("import os  # nosec B602\n", encoding="utf-8")

    orch_added = ReviewPipelineOrchestrator(
        session_id="test-added-supp",
        session_dir=tmp_path / "test-added-supp",
        target_dir=tmp_path,
    )
    orch_added.init_per_file_payloads(
        file_paths=["src/main.py"],
        metadata_by_path={},
        added_diff_lines={("src/main.py", 1)},
    )
    f_added = orch_added.admitted_scanner_findings[0]

    orch_base = ReviewPipelineOrchestrator(
        session_id="test-base-supp",
        session_dir=tmp_path / "test-base-supp",
        target_dir=tmp_path,
    )
    orch_base.init_per_file_payloads(
        file_paths=["src/main.py"],
        metadata_by_path={},
        added_diff_lines=set(),
    )
    f_base = orch_base.admitted_scanner_findings[0]

    assert (
        f_added.state,
        f_added.suppressed_by_change,
        f_base.state,
        f_base.suppressed_by_change,
    ) == (FindingState.OPEN, True, FindingState.SUPPRESSED, False)
