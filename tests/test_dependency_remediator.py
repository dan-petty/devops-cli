"""Unit tests for the automated dependency vulnerability remediation engine."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.exceptions import SecurityError
from devops_cli.models.vulnerability import (
    PackageLookupResult,
    VulnerabilityFixAction,
    VulnerabilityRecord,
    VulnerabilityRemediationResult,
)
from devops_cli.security.dependency_remediator import (
    DependencyRemediator,
    detect_lockfile_ecosystem,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake


def _upgrades(call: ProcessCall) -> bool:
    """Whether `call` is the lock upgrade of a remediation (uv's argv may carry preview flags)."""
    return "--upgrade-package" in call.argv


def _current_branch(repo: Path) -> str:
    """The branch that the working tree of `repo` is on."""
    return subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


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


def test_apply_remediation_success(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Test applying a planned remediation command successfully."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)
    process_fake.answer(_upgrades, ProcessAnswer(stdout="Lockfile updated"))

    action = VulnerabilityFixAction(
        package="demo-pkg",
        current_version="1.0.0",
        fixed_version="1.0.1",
        cve_id="CVE-2026-9999",
        upgrade_command=["uv", "lock", "--upgrade-package", "demo-pkg==1.0.1"],
    )

    res = remediator.apply_action(action)

    assert (res.status, res.error_message, [call.cwd for call in process_fake.calls]) == (
        "APPLIED",
        None,
        [tmp_path],
    )


def test_apply_remediation_failure(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Test handling remediation command failure gracefully."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)
    process_fake.answer(_upgrades, ProcessAnswer(returncode=1, stderr="Version conflict"))

    action = VulnerabilityFixAction(
        package="failing-pkg",
        current_version="1.0.0",
        fixed_version="2.0.0",
        cve_id="CVE-2026-0001",
        upgrade_command=["uv", "lock", "--upgrade-package", "failing-pkg==2.0.0"],
    )

    res = remediator.apply_action(action)

    assert (res.status, res.error_message) == ("FAILED", "Version conflict")


def test_remediate_with_git_branch(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Test full remediation execution with git branch creation."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    remediator = DependencyRemediator(target_dir=tmp_path)
    process_fake.answer(_upgrades, ProcessAnswer(stdout="Updated"))

    action = VulnerabilityFixAction(
        package="secure-lib",
        current_version="0.9.0",
        fixed_version="1.0.0",
        cve_id="GHSA-abcd-efgh",
        upgrade_command=["uv", "lock", "--upgrade-package", "secure-lib==1.0.0"],
    )

    result = remediator.remediate(actions=[action], create_branch=True)

    branch = "fix/security-secure-lib-ghsa-abcd-efgh"
    assert (
        result.applied_count,
        result.branch_name,
        ("git", "checkout", "-b", branch) in [call.argv for call in process_fake.calls],
    ) == (1, branch, True)


def test_cli_scan_fix_dry_run(tmp_path: Path, cli: Callable[..., Any]) -> None:
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

        res = cli(["scan", "fix", str(tmp_path), "--dry-run"])
        assert res.exit_code == 0
        assert "test-lib" in res.output
        assert "CVE-2026-1111" in res.output
        assert "PENDING" in res.output


def test_build_upgrade_commands_and_branch(tmp_path: Path, git: Callable[..., None]) -> None:
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

    git(tmp_path, "init", "-q")
    b_name = create_remediation_branch(tmp_path, "requests", "CVE:2026/1234")

    assert (b_name, _current_branch(tmp_path)) == (
        "fix/security-requests-cve-2026-1234",
        "fix/security-requests-cve-2026-1234",
    )


def _upgrade_action(**overrides: Any) -> VulnerabilityFixAction:
    return VulnerabilityFixAction(
        **{
            "package": "pkg",
            "current_version": "1.0",
            "cve_id": "CVE-2",
            "severity": "HIGH",
            "upgrade_command": ["false"],
            **overrides,
        }
    )


def test_an_action_with_no_upgrade_command_is_skipped(tmp_path: Path) -> None:
    """With nothing to run, the action is skipped."""
    remediator = DependencyRemediator(target_dir=tmp_path)

    result = remediator.apply_action(
        _upgrade_action(cve_id="CVE-1", severity="LOW", upgrade_command=[])
    )

    assert result.status == "SKIPPED"


def test_an_upgrade_command_that_exits_non_zero_fails_the_action_with_its_stderr(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A failed upgrade fails the action, and its error names what the command printed."""
    remediator = DependencyRemediator(target_dir=tmp_path)
    process_fake.answer("false", ProcessAnswer(returncode=1, stderr="Upgrade error"))

    result = remediator.apply_action(_upgrade_action())

    assert (result.status, "Upgrade error" in (result.error_message or "")) == ("FAILED", True)


def test_an_upgrade_command_that_raises_fails_the_action_with_the_error(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """An upgrade that cannot run fails the action, and its error names the cause."""
    remediator = DependencyRemediator(target_dir=tmp_path)
    process_fake.answer("false", ProcessAnswer(side_effect=RuntimeError("Subprocess timeout")))

    result = remediator.apply_action(_upgrade_action())

    assert (result.status, "Subprocess timeout" in (result.error_message or "")) == (
        "FAILED",
        True,
    )


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
        return_value=PackageLookupResult(status="ok", vulnerabilities=[mock_record]),
    ):
        result = remediator.scan_and_plan(package_filter="vulnerable-pkg")
        assert len(result.actions) == 1
        assert result.actions[0].package == "vulnerable-pkg"
        assert result.actions[0].fixed_version == "2.0.0"


def test_scan_and_plan_fails_when_the_osv_lookup_fails(tmp_path: Path) -> None:
    """A lookup that failed is not a package with nothing to fix: planning stops with the reason
    rather than offering an empty plan (#956)."""
    remediator = DependencyRemediator(target_dir=tmp_path)

    with (
        patch(
            "devops_cli.security.vulnerability_lookup.OSVClient.query_package",
            return_value=PackageLookupResult(status="failed", reason="OSV returned status 503"),
        ),
        pytest.raises(SecurityError) as failure,
    ):
        remediator.scan_and_plan(package_filter="vulnerable-pkg")

    assert (failure.value.message, failure.value.details) == (
        "OSV lookup failed for vulnerable-pkg: OSV returned status 503",
        {"package": "vulnerable-pkg", "reason": "OSV returned status 503"},
    )


def test_remediator_filter_mismatch_and_fallback_cmd() -> None:
    """Test unknown ecosystem fallback upgrade command and package_filter skipping."""
    from devops_cli.security.dependency_remediator import build_upgrade_command

    cmd = build_upgrade_command("UnknownEcosystem", "my-pkg", "1.2.3")
    assert cmd == ["uv", "lock", "--upgrade-package", "my-pkg==1.2.3"]

    remediator = DependencyRemediator()
    vuln = VulnerabilityRecord(id="CVE-2026-9999", package="other-pkg", severity="HIGH")
    plan = remediator.plan_remediation([vuln], package_filter="target-pkg")
    assert len(plan.actions) == 0


def test_create_remediation_branch_failure_returns_none(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Test create_remediation_branch returns None when git command fails."""
    from devops_cli.security.dependency_remediator import create_remediation_branch

    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "commit", "--allow-empty", "-q", "-m", "initial")
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    assert (
        create_remediation_branch(repo, "urllib3", "CVE-2026-0001"),
        create_remediation_branch(repo, "urllib3", "CVE-2026-0001"),
        create_remediation_branch(not_a_repo, "urllib3", "CVE-2026-0001"),
    ) == ("fix/security-urllib3-cve-2026-0001", None, None)


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
