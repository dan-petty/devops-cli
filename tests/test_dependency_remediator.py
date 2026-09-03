"""Unit tests for the automated dependency vulnerability remediation engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.scan import scan_app
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
