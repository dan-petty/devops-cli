"""Tests for declarative GitHub branch protection policy loader, auditor, and synchronizer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.branch_protection import (
    BranchProtectionAuditFinding,
    BranchProtectionAuditResult,
    BranchProtectionPolicy,
    BranchProtectionSyncResult,
    ReviewsPolicy,
    StatusChecksPolicy,
    audit_branch_protection,
    build_protection_payload,
    diff_branch_protection,
    get_remote_branch_protection,
    load_branch_protection_policies,
    sync_branch_protection,
)

runner = CliRunner()


@pytest.fixture
def sample_policy_yaml(tmp_path: Path) -> Path:
    content = """
- branch: "main"
  enforce_admins: true
  require_linear_history: true
  allow_force_pushes: false
  allow_deletions: false
  required_conversation_resolution: true
  required_status_checks:
    strict: true
    contexts:
      - "ci"
      - "pre-commit"
  required_pull_request_reviews:
    required_approving_review_count: 1
    dismiss_stale_reviews: true
    require_code_owner_reviews: true
    require_last_push_approval: true

- branch: "release/*"
  enforce_admins: true
  require_linear_history: true
  allow_force_pushes: false
  allow_deletions: false
  required_conversation_resolution: true
  required_status_checks:
    strict: true
    contexts:
      - "ci"
  required_pull_request_reviews:
    required_approving_review_count: 1
    dismiss_stale_reviews: true
    require_code_owner_reviews: true
    require_last_push_approval: true
"""
    file_path = tmp_path / "branch-protection.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_load_branch_protection_policies_success(sample_policy_yaml: Path) -> None:
    policies = load_branch_protection_policies(sample_policy_yaml)
    assert len(policies) == 2
    assert policies[0].branch == "main"
    assert policies[0].enforce_admins is True
    assert policies[0].required_status_checks.contexts == ["ci", "pre-commit"]
    assert policies[1].branch == "release/*"


def test_load_branch_protection_policies_missing_file(tmp_path: Path) -> None:
    with pytest.raises(GitHubOperationError) as exc_info:
        load_branch_protection_policies(tmp_path / "nonexistent.yml")
    assert "not found" in str(exc_info.value)


def test_load_branch_protection_policies_invalid_yaml(tmp_path: Path) -> None:
    bad_file = tmp_path / "invalid.yml"
    bad_file.write_text("invalid: [yaml: broken", encoding="utf-8")
    with pytest.raises(GitHubOperationError) as exc_info:
        load_branch_protection_policies(bad_file)
    assert "Failed to parse branch protection YAML" in str(exc_info.value)


def test_load_branch_protection_policies_not_a_list(tmp_path: Path) -> None:
    dict_file = tmp_path / "dict.yml"
    dict_file.write_text("branch: main\n", encoding="utf-8")
    with pytest.raises(GitHubOperationError) as exc_info:
        load_branch_protection_policies(dict_file)
    assert "Expected list of branch policies" in str(exc_info.value)


def test_load_branch_protection_policies_non_dict_item(tmp_path: Path) -> None:
    bad_item_file = tmp_path / "bad_item.yml"
    bad_item_file.write_text("- main\n- release\n", encoding="utf-8")
    with pytest.raises(GitHubOperationError) as exc_info:
        load_branch_protection_policies(bad_item_file)
    assert "must be a mapping" in str(exc_info.value)


def test_diff_branch_protection_unconfigured() -> None:
    policy = BranchProtectionPolicy(branch="main")
    result = diff_branch_protection(policy, remote=None)
    assert not result.is_compliant
    assert len(result.findings) == 1
    assert "completely unconfigured" in result.drift_summary[0]


def test_diff_branch_protection_fully_compliant() -> None:
    policy = BranchProtectionPolicy(
        branch="main",
        enforce_admins=True,
        require_linear_history=True,
        allow_force_pushes=False,
        allow_deletions=False,
        required_conversation_resolution=True,
        required_status_checks=StatusChecksPolicy(strict=True, contexts=["ci"]),
        required_pull_request_reviews=ReviewsPolicy(
            required_approving_review_count=1,
            dismiss_stale_reviews=True,
            require_code_owner_reviews=True,
            require_last_push_approval=True,
        ),
    )
    remote = {
        "enforce_admins": {"enabled": True},
        "required_linear_history": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
        "required_status_checks": {
            "strict": True,
            "contexts": ["ci"],
        },
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "require_last_push_approval": True,
        },
    }
    result = diff_branch_protection(policy, remote)
    assert result.is_compliant
    assert len(result.drift_summary) == 0


def test_diff_branch_protection_drift_detected() -> None:
    policy = BranchProtectionPolicy(
        branch="main",
        enforce_admins=True,
        require_linear_history=True,
        allow_force_pushes=False,
        required_status_checks=StatusChecksPolicy(strict=True, contexts=["ci", "lint"]),
        required_pull_request_reviews=ReviewsPolicy(required_approving_review_count=2),
    )
    remote = {
        "enforce_admins": {"enabled": False},
        "required_linear_history": {"enabled": False},
        "allow_force_pushes": {"enabled": True},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
        "required_status_checks": {
            "strict": False,
            "contexts": ["ci"],
        },
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "require_last_push_approval": True,
        },
    }
    result = diff_branch_protection(policy, remote)
    assert not result.is_compliant
    assert len(result.drift_summary) > 0
    drift_str = " ".join(result.drift_summary)
    assert "Strict status checks mismatch" in drift_str
    assert "Missing required status checks: lint" in drift_str
    assert "Review count mismatch" in drift_str
    assert "Enforce admins mismatch" in drift_str
    assert "require_linear_history mismatch" in drift_str
    assert "allow_force_pushes mismatch" in drift_str


def test_build_protection_payload() -> None:
    policy = BranchProtectionPolicy(
        branch="main",
        required_status_checks=StatusChecksPolicy(strict=True, contexts=["ci"]),
    )
    payload = build_protection_payload(policy)
    assert payload["enforce_admins"] is True
    assert payload["required_linear_history"] is True
    assert payload["required_status_checks"]["strict"] is True
    assert payload["required_status_checks"]["contexts"] == ["ci"]
    assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 1


@patch("devops_cli.github.branch_protection.run_gh")
def test_get_remote_branch_protection_success(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=0, stdout='{"enforce_admins": {"enabled": true}}')
    data = get_remote_branch_protection("dan-petty/devops-cli", "main")
    assert data is not None
    assert data["enforce_admins"]["enabled"] is True


@patch("devops_cli.github.branch_protection.run_gh")
def test_get_remote_branch_protection_not_found(mock_sub: MagicMock) -> None:
    mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="Not Found")
    data = get_remote_branch_protection("dan-petty/devops-cli", "main")
    assert data is None


@patch("devops_cli.github.branch_protection.get_remote_branch_protection")
def test_audit_branch_protection_branch_filter(mock_get: MagicMock) -> None:
    mock_get.return_value = None
    policies = [
        BranchProtectionPolicy(branch="main"),
        BranchProtectionPolicy(branch="release/*"),
    ]
    results = audit_branch_protection("dan-petty/devops-cli", policies, branch="main")
    assert len(results) == 1
    assert results[0].branch == "main"


@patch("devops_cli.github.branch_protection._apply_remote_protection")
@patch("devops_cli.github.branch_protection.get_remote_branch_protection")
def test_sync_branch_protection_dry_run(mock_get: MagicMock, mock_apply: MagicMock) -> None:
    mock_get.return_value = None  # Not compliant
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=True)
    assert res.dry_run is True
    assert "main" in res.synced_branches
    assert mock_apply.call_count == 0


@patch("devops_cli.github.branch_protection._apply_remote_protection")
@patch("devops_cli.github.branch_protection.get_remote_branch_protection")
def test_sync_branch_protection_live_success(mock_get: MagicMock, mock_apply: MagicMock) -> None:
    mock_get.return_value = None  # Not compliant
    mock_apply.return_value = True
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert res.dry_run is False
    assert "main" in res.synced_branches
    assert mock_apply.call_count == 1


@patch("devops_cli.github.branch_protection._apply_remote_protection")
@patch("devops_cli.github.branch_protection.get_remote_branch_protection")
def test_sync_branch_protection_already_compliant(
    mock_get: MagicMock, mock_apply: MagicMock
) -> None:
    mock_get.return_value = {
        "enforce_admins": True,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_conversation_resolution": True,
        "required_status_checks": {"strict": True, "contexts": []},
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "require_last_push_approval": True,
        },
    }
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert "main" in res.skipped_branches
    assert mock_apply.call_count == 0


@patch("devops_cli.github.branch_protection._apply_remote_protection")
@patch("devops_cli.github.branch_protection.get_remote_branch_protection")
def test_sync_branch_protection_failure(mock_get: MagicMock, mock_apply: MagicMock) -> None:
    mock_get.return_value = None
    mock_apply.return_value = False
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert "main" in res.failed_branches


@patch("devops_cli.commands.gh.audit_branch_protection")
@patch("devops_cli.commands.gh.load_branch_protection_policies")
def test_cli_branch_protection_audit_json(mock_load: MagicMock, mock_audit: MagicMock) -> None:
    mock_load.return_value = [BranchProtectionPolicy(branch="main")]
    mock_audit.return_value = [
        BranchProtectionAuditResult(branch="main", is_compliant=True, findings=[], drift_summary=[])
    ]
    res = runner.invoke(
        app, ["branch-protection", "audit", "--repo", "dan-petty/devops-cli", "--json"]
    )
    assert res.exit_code == 0
    parsed = json.loads(res.stdout)
    assert parsed[0]["branch"] == "main"
    assert parsed[0]["is_compliant"] is True


@patch("devops_cli.commands.gh.audit_branch_protection")
@patch("devops_cli.commands.gh.load_branch_protection_policies")
def test_cli_branch_protection_audit_drift_warning(
    mock_load: MagicMock, mock_audit: MagicMock
) -> None:
    mock_load.return_value = [BranchProtectionPolicy(branch="main")]
    mock_audit.return_value = [
        BranchProtectionAuditResult(
            branch="main",
            is_compliant=False,
            findings=[
                BranchProtectionAuditFinding(
                    branch="main",
                    setting="admin",
                    expected=True,
                    actual=False,
                    compliant=False,
                    message="Admin enforcement mismatch",
                )
            ],
            drift_summary=["Admin enforcement mismatch"],
        )
    ]
    res = runner.invoke(app, ["branch-protection", "audit", "--repo", "dan-petty/devops-cli"])
    assert res.exit_code == 0
    assert "drift detected" in res.stdout.lower()


@patch("devops_cli.commands.gh.sync_branch_protection")
@patch("devops_cli.commands.gh.load_branch_protection_policies")
def test_cli_branch_protection_sync_dry_run(mock_load: MagicMock, mock_sync: MagicMock) -> None:
    mock_load.return_value = [BranchProtectionPolicy(branch="main")]
    mock_sync.return_value = BranchProtectionSyncResult(
        synced_branches=["main"], skipped_branches=[], failed_branches=[], dry_run=True
    )
    res = runner.invoke(
        app,
        ["branch-protection", "sync", "--repo", "dan-petty/devops-cli", "--dry-run"],
    )
    assert res.exit_code == 0
    assert "DRY RUN" in res.stdout
    assert "1 synced" in res.stdout
