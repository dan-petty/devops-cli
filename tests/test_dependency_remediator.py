"""Unit tests for the automated dependency vulnerability remediation engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
from devops_cli.models.vulnerability import (
    VulnerabilityFixAction,
    VulnerabilityRecord,
    VulnerabilityRemediationResult,
)
from devops_cli.security.dependency_remediator import (
    DependencyRemediator,
    detect_lockfile_ecosystem,
)

runner = CliRunner()


def test_detect_lockfile_ecosystem(tmp_path: Path) -> None:
    """Test ecosystem and lockfile detection across ecosystems."""
    # PyPI / uv
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    eco, lock = detect_lockfile_ecosystem(tmp_path)
    assert eco == "PyPI"
    assert lock == "uv.lock"

    # npm
    npm_path = tmp_path / "npm_project"
    npm_path.mkdir()
    (npm_path / "package-lock.json").write_text("{}", encoding="utf-8")
    eco, lock = detect_lockfile_ecosystem(npm_path)
    assert eco == "npm"
    assert lock == "package-lock.json"

    # Rust
    cargo_path = tmp_path / "rust_project"
    cargo_path.mkdir()
    (cargo_path / "Cargo.lock").write_text("", encoding="utf-8")
    eco, lock = detect_lockfile_ecosystem(cargo_path)
    assert eco == "crates.io"
    assert lock == "Cargo.lock"

    # Go
    go_path = tmp_path / "go_project"
    go_path.mkdir()
    (go_path / "go.sum").write_text("", encoding="utf-8")
    eco, lock = detect_lockfile_ecosystem(go_path)
    assert eco == "Go"
    assert lock == "go.sum"


def test_plan_remediation_dry_run(tmp_path: Path) -> None:
    """Test planning a dependency vulnerability fix in dry-run mode."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)

    vuln = VulnerabilityRecord(
        id="GHSA-1234-5678",
        summary="Remote code execution in vulnerable-pkg",
        severity="HIGH",
        package="vulnerable-pkg",
        affected_version_range="<2.0.0",
        fixed_version="2.0.0",
        source="OSV",
    )

    result = remediator.plan_remediation(
        vulnerabilities=[vuln],
        installed_versions={"vulnerable-pkg": "1.9.0"},
    )

    assert result.ecosystem == "PyPI"
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.package == "vulnerable-pkg"
    assert action.current_version == "1.9.0"
    assert action.fixed_version == "2.0.0"
    assert action.status == "PENDING"
    assert "--upgrade-package" in action.upgrade_command
    assert "vulnerable-pkg==2.0.0" in action.upgrade_command


def test_apply_remediation_success(tmp_path: Path) -> None:
    """Test applying a planned remediation command successfully."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)

    action = VulnerabilityFixAction(
        package="demo-pkg",
        current_version="1.0.0",
        fixed_version="1.0.1",
        cve_id="CVE-2026-9999",
        upgrade_command=["uv", "lock", "--upgrade-package", "demo-pkg==1.0.1"],
    )

    with patch("devops_cli.security.dependency_remediator.run_subprocess") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stdout="Lockfile updated", stderr="")
        res = remediator.apply_action(action)
        assert res.status == "APPLIED"
        assert res.error_message is None
        assert mock_sub.called


def test_apply_remediation_failure(tmp_path: Path) -> None:
    """Test handling remediation command failure gracefully."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)

    action = VulnerabilityFixAction(
        package="failing-pkg",
        current_version="1.0.0",
        fixed_version="2.0.0",
        cve_id="CVE-2026-0001",
        upgrade_command=["uv", "lock", "--upgrade-package", "failing-pkg==2.0.0"],
    )

    with patch("devops_cli.security.dependency_remediator.run_subprocess") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="Version conflict")
        res = remediator.apply_action(action)
        assert res.status == "FAILED"
        assert res.error_message == "Version conflict"


def test_remediate_with_git_branch(tmp_path: Path) -> None:
    """Test full remediation execution with git branch creation."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)

    action = VulnerabilityFixAction(
        package="secure-lib",
        current_version="0.9.0",
        fixed_version="1.0.0",
        cve_id="GHSA-abcd-efgh",
        upgrade_command=["uv", "lock", "--upgrade-package", "secure-lib==1.0.0"],
    )

    with (
        patch("devops_cli.security.dependency_remediator.run_subprocess") as mock_sub,
        patch("devops_cli.security.dependency_remediator.create_remediation_branch") as mock_branch,
    ):
        mock_sub.return_value = MagicMock(returncode=0, stdout="Updated", stderr="")
        mock_branch.return_value = "fix/security-secure-lib-GHSA-abcd-efgh"

        result = remediator.remediate(
            actions=[action],
            create_branch=True,
        )

        assert result.applied_count == 1
        assert result.branch_name == "fix/security-secure-lib-GHSA-abcd-efgh"
        assert mock_branch.called


def test_cli_scan_fix_dry_run(tmp_path: Path) -> None:
    """Test devops scan fix CLI command in dry-run mode."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")

    with patch(
        "devops_cli.security.dependency_remediator.DependencyRemediator.scan_and_plan"
    ) as mock_plan:
        mock_plan.return_value = VulnerabilityRemediationResult(
            target_path=str(tmp_path),
            ecosystem="PyPI",
            actions=[
                VulnerabilityFixAction(
                    package="test-lib",
                    current_version="1.0.0",
                    fixed_version="1.1.0",
                    cve_id="CVE-2026-1111",
                    severity="HIGH",
                    upgrade_command=["uv", "lock", "--upgrade-package", "test-lib==1.1.0"],
                    status="PENDING",
                )
            ],
            summary="Planned 1 vulnerability remediation",
        )

        res = runner.invoke(scan_app, ["fix", str(tmp_path), "--dry-run"])
        assert res.exit_code == 0
        assert "test-lib" in res.output
        assert "CVE-2026-1111" in res.output
        assert "PENDING" in res.output


def test_build_upgrade_commands_and_branch(tmp_path: Path) -> None:
    """Test build_upgrade_command and create_remediation_branch."""
    from devops_cli.security.dependency_remediator import (
        build_upgrade_command,
        create_remediation_branch,
    )

    assert build_upgrade_command("npm", "lodash", "4.17.21") == ["npm", "update", "lodash==4.17.21"]
    assert build_upgrade_command("crates.io", "serde", "1.0.0") == [
        "cargo",
        "update",
        "-p",
        "serde",
    ]
    assert build_upgrade_command("Go", "golang.org/x/crypto", "0.1.0") == [
        "go",
        "get",
        "-u",
        "golang.org/x/crypto==0.1.0",
    ]

    with patch("devops_cli.security.dependency_remediator.run_subprocess") as mock_subproc:
        mock_subproc.return_value = MagicMock(returncode=0)
        b_name = create_remediation_branch(tmp_path, "requests", "CVE:2026/1234")
        assert b_name == "fix/security-requests-cve-2026-1234"
        assert mock_subproc.called


def test_apply_action_edge_cases(tmp_path: Path) -> None:
    """Test apply_action skipped, failed returncode, and exception branches."""
    remediator = DependencyRemediator(target_dir=tmp_path)

    # 1. Skipped when upgrade_command is empty
    act_empty = VulnerabilityFixAction(
        package="pkg",
        current_version="1.0",
        cve_id="CVE-1",
        severity="LOW",
        upgrade_command=[],
    )
    res_empty = remediator.apply_action(act_empty)
    assert res_empty.status == "SKIPPED"

    # 2. Failed when subprocess fails
    act_fail = VulnerabilityFixAction(
        package="pkg",
        current_version="1.0",
        cve_id="CVE-2",
        severity="HIGH",
        upgrade_command=["false"],
    )
    with patch(
        "devops_cli.security.dependency_remediator.run_subprocess",
        return_value=MagicMock(returncode=1, stderr="Upgrade error", stdout=""),
    ):
        res_fail = remediator.apply_action(act_fail)
        assert res_fail.status == "FAILED"
        assert "Upgrade error" in (res_fail.error_message or "")

    # 3. Exception caught
    with patch(
        "devops_cli.security.dependency_remediator.run_subprocess",
        side_effect=RuntimeError("Subprocess timeout"),
    ):
        res_exc = remediator.apply_action(act_fail)
        assert res_exc.status == "FAILED"
        assert "Subprocess timeout" in (res_exc.error_message or "")


def test_scan_and_plan_with_osv(tmp_path: Path) -> None:
    """Test scan_and_plan calling OSVClient."""
    remediator = DependencyRemediator(target_dir=tmp_path)

    mock_record = VulnerabilityRecord(
        id="GHSA-test-1234",
        package="vulnerable-pkg",
        severity="HIGH",
        fixed_version="2.0.0",
    )

    with patch(
        "devops_cli.security.vulnerability_lookup.OSVClient.query_package",
        return_value=[mock_record],
    ):
        result = remediator.scan_and_plan(package_filter="vulnerable-pkg")
        assert len(result.actions) == 1
        assert result.actions[0].package == "vulnerable-pkg"
        assert result.actions[0].fixed_version == "2.0.0"


def test_remediator_filter_mismatch_and_fallback_cmd() -> None:
    """Test unknown ecosystem fallback upgrade command and package_filter skipping."""
    from devops_cli.security.dependency_remediator import build_upgrade_command

    cmd = build_upgrade_command("UnknownEcosystem", "my-pkg", "1.2.3")
    assert cmd == ["uv", "lock", "--upgrade-package", "my-pkg==1.2.3"]

    remediator = DependencyRemediator()
    vuln = VulnerabilityRecord(id="CVE-2026-9999", package="other-pkg", severity="HIGH")
    plan = remediator.plan_remediation([vuln], package_filter="target-pkg")
    assert len(plan.actions) == 0


def test_create_remediation_branch_failure_returns_none(tmp_path: Path) -> None:
    """Test create_remediation_branch returns None when git command fails."""
    from devops_cli.security.dependency_remediator import create_remediation_branch

    # Success case (returncode=0)
    with patch("devops_cli.security.dependency_remediator.run_subprocess") as mock_subproc:
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")
        b_name = create_remediation_branch(tmp_path, "urllib3", "CVE-2026-0001")
        assert b_name == "fix/security-urllib3-cve-2026-0001"

    # Failure case (returncode != 0 e.g. branch exists or not git repo)
    with patch("devops_cli.security.dependency_remediator.run_subprocess") as mock_subproc:
        mock_subproc.return_value = MagicMock(
            returncode=128, stdout="", stderr="fatal: not a git repo"
        )
        b_name = create_remediation_branch(tmp_path, "urllib3", "CVE-2026-0001")
        assert b_name is None


def test_plan_remediation_min_severity_filtering() -> None:
    """Test that plan_remediation respects min_severity threshold."""
    remediator = DependencyRemediator()
    vulns = [
        VulnerabilityRecord(id="V-1", package="p1", severity="LOW"),
        VulnerabilityRecord(id="V-2", package="p2", severity="MEDIUM"),
        VulnerabilityRecord(id="V-3", package="p3", severity="HIGH"),
        VulnerabilityRecord(id="V-4", package="p4", severity="CRITICAL"),
    ]

    # min_severity=CRITICAL -> only CRITICAL
    plan_crit = remediator.plan_remediation(vulns, min_severity="CRITICAL")
    assert [a.package for a in plan_crit.actions] == ["p4"]

    # min_severity=HIGH -> HIGH and CRITICAL
    plan_high = remediator.plan_remediation(vulns, min_severity="HIGH")
    assert [a.package for a in plan_high.actions] == ["p3", "p4"]

    # min_severity=MEDIUM -> MEDIUM, HIGH, and CRITICAL
    plan_med = remediator.plan_remediation(vulns, min_severity="MEDIUM")
    assert [a.package for a in plan_med.actions] == ["p2", "p3", "p4"]

    # min_severity=LOW -> all
    plan_low = remediator.plan_remediation(vulns, min_severity="LOW")
    assert [a.package for a in plan_low.actions] == ["p1", "p2", "p3", "p4"]


def test_scan_and_plan_without_package_filter(tmp_path: Path) -> None:
    """Test scan_and_plan scans workspace vulnerabilities when package_filter is None."""
    remediator = DependencyRemediator(target_dir=tmp_path)

    from devops_cli.ai.review_schema import Finding

    mock_findings = [
        Finding(
            severity="HIGH",
            location="uv.lock:jinja2",
            title="[CVE-2026-1234] Vulnerability in jinja2",
            description="High vulnerability",
            fix="Upgrade jinja2",
            confidence_score=None,
        ),
        Finding(
            severity="LOW",
            location="uv.lock:requests",
            title="[CVE-2026-5678] Low issue in requests",
            description="Low vulnerability",
            fix="Upgrade requests",
            confidence_score=None,
        ),
    ]

    with patch("devops_cli.security.trivy.run_trivy_scan", return_value=mock_findings):
        # min_severity=HIGH filters out LOW
        res = remediator.scan_and_plan(package_filter=None, min_severity="HIGH")
        assert len(res.actions) == 1
        assert res.actions[0].package == "jinja2"
        assert res.actions[0].severity == "HIGH"
