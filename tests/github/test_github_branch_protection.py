"""Tests for declarative GitHub branch protection policy loader, auditor, and synchronizer."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.branch_protection import (
    BranchProtectionPolicy,
    ReviewsPolicy,
    StatusChecksPolicy,
    apply_remote_protection,
    audit_branch_protection,
    build_protection_payload,
    diff_branch_protection,
    get_remote_branch_protection,
    load_branch_protection_policies,
    sync_branch_protection,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake

if TYPE_CHECKING:
    from tests.support.cli import CliRunnerFixture


@pytest.fixture(autouse=True)
def _answer_rate_limit(process_fake: ProcessFake) -> None:
    fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(
            stdout=json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
        ),
    )


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

- branch: "stable/*"
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


def test_load_branch_protection_policies_reads_valid_yaml(sample_policy_yaml: Path) -> None:
    policies = load_branch_protection_policies(sample_policy_yaml)
    assert len(policies) == 2
    assert policies[0].branch == "main"
    assert policies[0].enforce_admins is True
    assert policies[0].required_status_checks.contexts == ["ci", "pre-commit"]
    assert policies[1].branch == "stable/*"


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


def test_get_remote_branch_protection_returns_payload(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=0, stdout='{"enforce_admins": {"enabled": true}}'),
    )
    data = get_remote_branch_protection("dan-petty/devops-cli", "main")
    assert data is not None
    assert data["enforce_admins"]["enabled"] is True


def test_get_remote_branch_protection_not_found(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stdout="", stderr="gh: HTTP 404: Branch not protected"),
    )
    data = get_remote_branch_protection("dan-petty/devops-cli", "main")
    assert data is None


@pytest.mark.parametrize(
    "stderr_payload",
    [
        pytest.param(
            "gh: HTTP 404: Not Found (https://api.github.com/repos/org/repo)",
            id="repository-not-found",
        ),
        pytest.param("Internal Server Error (HTTP 500)", id="server-error"),
    ],
)
def test_get_remote_branch_protection_api_failure_raises(
    process_fake: ProcessFake, stderr_payload: str
) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stdout="", stderr=stderr_payload),
    )
    with pytest.raises(GitHubOperationError) as exc_info:
        get_remote_branch_protection("dan-petty/devops-cli", "main")
    assert "Failed to fetch branch protection" in str(exc_info.value)


def test_get_remote_branch_protection_json_error(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=0, stdout="broken json", stderr=""),
    )
    with pytest.raises(GitHubOperationError) as exc_info:
        get_remote_branch_protection("dan-petty/devops-cli", "main")
    assert "Failed to parse protection JSON" in str(exc_info.value)


def test_apply_remote_protection_error(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "-X", "PUT", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stdout="", stderr="Forbidden"),
    )
    with pytest.raises(GitHubOperationError) as exc_info:
        apply_remote_protection("dan-petty/devops-cli", "main", {})
    assert "Failed to update branch protection" in str(exc_info.value)


def test_audit_branch_protection_branch_filter(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stderr="gh: HTTP 404: Branch not protected"),
    )
    policies = [
        BranchProtectionPolicy(branch="main"),
        BranchProtectionPolicy(branch="stable/*"),
    ]
    results = audit_branch_protection("dan-petty/devops-cli", policies, branch="main")
    assert len(results) == 1
    assert results[0].branch == "main"


def test_sync_branch_protection_dry_run(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stderr="gh: HTTP 404: Branch not protected"),
    )
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=True)
    assert res.dry_run is True
    assert "main" in res.synced_branches
    assert not any(call.argv[1:4] == ("api", "-X", "PUT") for call in process_fake.calls)


def test_sync_branch_protection_live_updates_remote(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stderr="gh: HTTP 404: Branch not protected"),
    )
    process_fake.answer(
        ["gh", "api", "-X", "PUT", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=0, stdout=""),
    )
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert res.dry_run is False
    assert "main" in res.synced_branches
    assert any(call.argv[1:4] == ("api", "-X", "PUT") for call in process_fake.calls)


def test_sync_branch_protection_already_compliant(process_fake: ProcessFake) -> None:
    compliant = {
        "enforce_admins": {"enabled": True},
        "required_linear_history": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
        "required_status_checks": {"strict": True, "contexts": []},
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "require_last_push_approval": True,
        },
    }
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=0, stdout=json.dumps(compliant)),
    )
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert "main" in res.skipped_branches
    assert not any(call.argv[1:4] == ("api", "-X", "PUT") for call in process_fake.calls)


def test_sync_branch_protection_handles_apply_error(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stderr="gh: HTTP 404: Branch not protected"),
    )
    process_fake.answer(
        ["gh", "api", "-X", "PUT", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stderr="Sync failed"),
    )
    policies = [BranchProtectionPolicy(branch="main")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert "main" in res.failed_branches


def test_sync_branch_protection_fetch_fails(process_fake: ProcessFake, clock: ClockFake) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=1, stderr="API rate limit exceeded"),
    )
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/stable/*/protection"],
        ProcessAnswer(returncode=1, stderr="API rate limit exceeded"),
    )
    policies = [BranchProtectionPolicy(branch="main"), BranchProtectionPolicy(branch="stable/*")]
    res = sync_branch_protection("dan-petty/devops-cli", policies, dry_run=False)
    assert res.failed_branches == ["main", "stable/*"]


def test_cli_branch_protection_audit_json(
    cli: CliRunnerFixture, process_fake: ProcessFake, sample_policy_yaml: Path
) -> None:
    compliant = {
        "enforce_admins": {"enabled": True},
        "required_linear_history": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
        "required_status_checks": {"strict": True, "contexts": ["ci", "pre-commit"]},
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "require_last_push_approval": True,
        },
    }
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=0, stdout=json.dumps(compliant)),
    )
    res = cli(
        "gh",
        "branch-protection",
        "audit",
        "--repo",
        "dan-petty/devops-cli",
        "--branch",
        "main",
        "--policy-file",
        str(sample_policy_yaml),
        "--json",
    )
    assert res.exit_code == 0
    parsed = json.loads(res.output)
    assert parsed[0]["branch"] == "main"
    assert parsed[0]["is_compliant"] is True


def test_cli_branch_protection_audit_drift_warning(
    cli: CliRunnerFixture, process_fake: ProcessFake, sample_policy_yaml: Path
) -> None:
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/branches/main/protection"],
        ProcessAnswer(returncode=0, stdout=json.dumps({"enforce_admins": {"enabled": False}})),
    )
    res = cli(
        "gh",
        "branch-protection",
        "audit",
        "--repo",
        "dan-petty/devops-cli",
        "--branch",
        "main",
        "--policy-file",
        str(sample_policy_yaml),
    )
    assert res.exit_code == 0
    assert "drift detected" in res.output.lower()


def test_cli_branch_protection_sync_dry_run(
    cli: CliRunnerFixture, sample_policy_yaml: Path
) -> None:
    res = cli(
        "gh",
        "branch-protection",
        "sync",
        "--repo",
        "dan-petty/devops-cli",
        "--branch",
        "main",
        "--policy-file",
        str(sample_policy_yaml),
        "--dry-run",
    )
    assert res.exit_code == 0
    assert "Plan for synchronizing branch protection (dan-petty/devops-cli)" in res.output
    assert "gh api -X PUT repos/dan-petty/devops-cli/branches/main/protection" in res.output


def test_cli_branch_protection_help_mentions_classic_and_rulesets(cli: CliRunnerFixture) -> None:
    res = cli("gh", "branch-protection", "--help")
    assert res.exit_code == 0
    assert "classic" in res.output
    assert "rulesets" in res.output


def test_cli_branch_protection_audit_missing_policy_file(cli: CliRunnerFixture) -> None:
    res = cli(
        "gh",
        "branch-protection",
        "audit",
        "--repo",
        "dan-petty/devops-cli",
        "--policy-file",
        "nonexistent.yml",
    )
    assert res.exit_code == 1
    assert "Failed to load branch protection policies" in res.output
