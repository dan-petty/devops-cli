"""Declarative GitHub branch protection policy loading, auditing, and synchronization."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class StatusChecksPolicy(BaseModel):
    """Declarative status checks policy for protected branch."""

    strict: bool = True
    contexts: list[str] = Field(default_factory=list)


class ReviewsPolicy(BaseModel):
    """Declarative pull request review policy for protected branch."""

    required_approving_review_count: int = 1
    dismiss_stale_reviews: bool = True
    require_code_owner_reviews: bool = True
    require_last_push_approval: bool = True


class BranchProtectionPolicy(BaseModel):
    """Declarative specification for branch protection rules."""

    branch: str
    enforce_admins: bool = True
    require_linear_history: bool = True
    allow_force_pushes: bool = False
    allow_deletions: bool = False
    required_conversation_resolution: bool = True
    required_status_checks: StatusChecksPolicy = Field(default_factory=StatusChecksPolicy)
    required_pull_request_reviews: ReviewsPolicy = Field(default_factory=ReviewsPolicy)


class BranchProtectionAuditFinding(BaseModel):
    """Single audit finding representing a policy divergence on a protected branch."""

    branch: str
    setting: str
    expected: Any
    actual: Any
    compliant: bool
    message: str = ""


class BranchProtectionAuditResult(BaseModel):
    """Audit outcome for a branch against its declarative protection policy."""

    branch: str
    is_compliant: bool = True
    findings: list[BranchProtectionAuditFinding] = Field(default_factory=list)
    drift_summary: list[str] = Field(default_factory=list)


class BranchProtectionSyncResult(BaseModel):
    """Summary of branch protection synchronization across declared branches."""

    synced_branches: list[str] = Field(default_factory=list)
    skipped_branches: list[str] = Field(default_factory=list)
    failed_branches: list[str] = Field(default_factory=list)
    dry_run: bool = False


def load_branch_protection_policies(
    path: Path = Path(".github/branch-protection.yml"),
) -> list[BranchProtectionPolicy]:
    """Load and validate declarative branch protection policies from YAML file."""
    if not path.is_file():
        raise GitHubOperationError(
            f"Branch protection policy file not found: {path}",
            operation="load_branch_protection_policies",
            details={"path": str(path)[:256]},
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GitHubOperationError(
            f"Failed to parse branch protection YAML {path}: {exc}",
            operation="load_branch_protection_policies",
            details={"path": str(path)[:256], "error": str(exc)[:256]},
        ) from exc

    if not isinstance(raw, list):
        raise GitHubOperationError(
            f"Expected list of branch policies in {path}, got {type(raw).__name__}",
            operation="load_branch_protection_policies",
            details={"path": str(path)[:256]},
        )

    policies: list[BranchProtectionPolicy] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise GitHubOperationError(
                f"Policy item #{idx} must be a mapping, got {type(item).__name__}",
                operation="load_branch_protection_policies",
                details={"index": idx},
            )
        policies.append(BranchProtectionPolicy(**item))

    return policies


def _extract_enabled_flag(value: Any) -> bool:
    """Extract boolean flag whether value is a raw bool or an object with an enabled key."""
    if isinstance(value, dict):
        return bool(value.get("enabled", False))
    if isinstance(value, bool):
        return value
    return False


def _is_branch_unprotected_error(err_msg: str) -> bool:
    """Predicate determining if gh api error output indicates an unprotected branch."""
    err_lower = err_msg.lower()
    if "branch not protected" in err_lower:
        return True
    return "404" in err_msg and ("branch" in err_lower or "protection" in err_lower)


def get_remote_branch_protection(repo: str, branch: str) -> dict[str, Any] | None:
    """Fetch branch protection configuration from GitHub REST API via gh cli."""
    with trace_span("github.branch_protection.get", attributes={"repo": repo, "branch": branch}):
        cmd = [CONST_GH_CLI, "api", f"repos/{repo}/branches/{branch}/protection"]
        res = run_gh(cmd, check=False, quiet=True)
        if res.returncode != 0:
            err_msg = (res.stderr or "").strip()
            if _is_branch_unprotected_error(err_msg):
                logger.debug("Branch %s has no remote protection: %s", branch, err_msg)
                return None
            raise GitHubOperationError(
                f"Failed to fetch branch protection for {branch} on {repo}: {err_msg}",
                operation="get_remote_branch_protection",
                details={
                    "repo": repo,
                    "branch": branch,
                    "exit_code": res.returncode,
                    "stderr": err_msg[:256],
                },
            )
        if not res.stdout.strip():
            return None

        try:
            data: dict[str, Any] = json.loads(res.stdout)
            return data
        except json.JSONDecodeError as exc:
            raise GitHubOperationError(
                f"Failed to parse protection JSON for {branch}: {exc}",
                operation="get_remote_branch_protection",
                details={"repo": repo, "branch": branch, "error": str(exc)[:256]},
            ) from exc


def _diff_status_checks(
    branch: str,
    policy: StatusChecksPolicy,
    remote: dict[str, Any] | None,
) -> list[BranchProtectionAuditFinding]:
    """Audit status checks compliance."""
    findings: list[BranchProtectionAuditFinding] = []
    checks_data = (remote or {}).get("required_status_checks") or {}

    remote_strict = bool(checks_data.get("strict", False))
    if remote_strict != policy.strict:
        findings.append(
            BranchProtectionAuditFinding(
                branch=branch,
                setting="required_status_checks.strict",
                expected=policy.strict,
                actual=remote_strict,
                compliant=False,
                message=f"Strict status checks mismatch (expected {policy.strict}, got {remote_strict})",
            )
        )

    remote_contexts = set(checks_data.get("contexts", []))
    expected_contexts = set(policy.contexts)
    missing_contexts = sorted(expected_contexts - remote_contexts)
    if missing_contexts:
        findings.append(
            BranchProtectionAuditFinding(
                branch=branch,
                setting="required_status_checks.contexts",
                expected=policy.contexts,
                actual=list(remote_contexts),
                compliant=False,
                message=f"Missing required status checks: {', '.join(missing_contexts)}",
            )
        )

    return findings


def _diff_pr_reviews(
    branch: str,
    policy: ReviewsPolicy,
    remote: dict[str, Any] | None,
) -> list[BranchProtectionAuditFinding]:
    """Audit PR review policy compliance."""
    findings: list[BranchProtectionAuditFinding] = []
    reviews_data = (remote or {}).get("required_pull_request_reviews") or {}

    actual_count = int(reviews_data.get("required_approving_review_count", 0))
    if actual_count != policy.required_approving_review_count:
        findings.append(
            BranchProtectionAuditFinding(
                branch=branch,
                setting="required_pull_request_reviews.required_approving_review_count",
                expected=policy.required_approving_review_count,
                actual=actual_count,
                compliant=False,
                message=f"Review count mismatch (expected {policy.required_approving_review_count}, got {actual_count})",
            )
        )

    flags = [
        ("dismiss_stale_reviews", policy.dismiss_stale_reviews),
        ("require_code_owner_reviews", policy.require_code_owner_reviews),
        ("require_last_push_approval", policy.require_last_push_approval),
    ]
    for key, expected_val in flags:
        actual_val = bool(reviews_data.get(key, False))
        if actual_val != expected_val:
            findings.append(
                BranchProtectionAuditFinding(
                    branch=branch,
                    setting=f"required_pull_request_reviews.{key}",
                    expected=expected_val,
                    actual=actual_val,
                    compliant=False,
                    message=f"{key} mismatch (expected {expected_val}, got {actual_val})",
                )
            )

    return findings


def _diff_boolean_flags(
    branch: str,
    policy: BranchProtectionPolicy,
    remote: dict[str, Any] | None,
) -> list[BranchProtectionAuditFinding]:
    """Audit top-level protection flags."""
    findings: list[BranchProtectionAuditFinding] = []
    remote_data = remote or {}

    admin_actual = _extract_enabled_flag(remote_data.get("enforce_admins"))
    if admin_actual != policy.enforce_admins:
        findings.append(
            BranchProtectionAuditFinding(
                branch=branch,
                setting="enforce_admins",
                expected=policy.enforce_admins,
                actual=admin_actual,
                compliant=False,
                message=f"Enforce admins mismatch (expected {policy.enforce_admins}, got {admin_actual})",
            )
        )

    flag_pairs = [
        ("require_linear_history", policy.require_linear_history, "required_linear_history"),
        ("allow_force_pushes", policy.allow_force_pushes, "allow_force_pushes"),
        ("allow_deletions", policy.allow_deletions, "allow_deletions"),
        (
            "required_conversation_resolution",
            policy.required_conversation_resolution,
            "required_conversation_resolution",
        ),
    ]
    for setting_name, expected_val, remote_key in flag_pairs:
        actual_val = _extract_enabled_flag(remote_data.get(remote_key))
        if actual_val != expected_val:
            findings.append(
                BranchProtectionAuditFinding(
                    branch=branch,
                    setting=setting_name,
                    expected=expected_val,
                    actual=actual_val,
                    compliant=False,
                    message=f"{setting_name} mismatch (expected {expected_val}, got {actual_val})",
                )
            )

    return findings


def diff_branch_protection(
    policy: BranchProtectionPolicy,
    remote: dict[str, Any] | None,
) -> BranchProtectionAuditResult:
    """Compare desired policy with current remote protection settings."""
    if remote is None:
        return BranchProtectionAuditResult(
            branch=policy.branch,
            is_compliant=False,
            findings=[
                BranchProtectionAuditFinding(
                    branch=policy.branch,
                    setting="protection_enabled",
                    expected=True,
                    actual=False,
                    compliant=False,
                    message="Branch protection is completely unconfigured on remote",
                )
            ],
            drift_summary=["Branch protection is completely unconfigured on remote"],
        )

    findings: list[BranchProtectionAuditFinding] = []
    findings.extend(_diff_status_checks(policy.branch, policy.required_status_checks, remote))
    findings.extend(_diff_pr_reviews(policy.branch, policy.required_pull_request_reviews, remote))
    findings.extend(_diff_boolean_flags(policy.branch, policy, remote))

    drift = [f.message for f in findings if not f.compliant]
    return BranchProtectionAuditResult(
        branch=policy.branch,
        is_compliant=len(drift) == 0,
        findings=findings,
        drift_summary=drift,
    )


def audit_branch_protection(
    repo: str,
    policies: list[BranchProtectionPolicy],
    branch: str | None = None,
) -> list[BranchProtectionAuditResult]:
    """Audit branch protection settings against declared policies."""
    target_policies = [p for p in policies if branch is None or p.branch == branch]
    results: list[BranchProtectionAuditResult] = []

    for pol in target_policies:
        remote = get_remote_branch_protection(repo, pol.branch)
        results.append(diff_branch_protection(pol, remote))

    return results


def build_protection_payload(policy: BranchProtectionPolicy) -> dict[str, Any]:
    """Build GitHub REST API request payload for updating branch protection."""
    return {
        "required_status_checks": {
            "strict": policy.required_status_checks.strict,
            "contexts": policy.required_status_checks.contexts,
        },
        "enforce_admins": policy.enforce_admins,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": policy.required_pull_request_reviews.dismiss_stale_reviews,
            "require_code_owner_reviews": policy.required_pull_request_reviews.require_code_owner_reviews,
            "required_approving_review_count": policy.required_pull_request_reviews.required_approving_review_count,
            "require_last_push_approval": policy.required_pull_request_reviews.require_last_push_approval,
        },
        "restrictions": None,
        "required_linear_history": policy.require_linear_history,
        "allow_force_pushes": policy.allow_force_pushes,
        "allow_deletions": policy.allow_deletions,
        "required_conversation_resolution": policy.required_conversation_resolution,
    }


def _apply_remote_protection(repo: str, branch: str, payload: dict[str, Any]) -> bool:
    """Push branch protection update to GitHub via gh CLI."""
    cmd = [
        CONST_GH_CLI,
        "api",
        "-X",
        "PUT",
        f"repos/{repo}/branches/{branch}/protection",
        "--input",
        "-",
    ]
    payload_str = json.dumps(payload)
    res = run_gh(cmd, input=payload_str, check=False, quiet=True)
    if res.returncode != 0:
        err_msg = (res.stderr or "").strip()
        logger.error(
            "Failed to update branch protection for %s on %s: %s",
            branch,
            repo,
            err_msg[:256],
        )
        raise GitHubOperationError(
            f"Failed to update branch protection for {branch} on {repo}: {err_msg}",
            operation="apply_remote_protection",
            details={
                "repo": repo,
                "branch": branch,
                "exit_code": res.returncode,
                "stderr": err_msg[:256],
            },
        )
    return True


def sync_branch_protection(
    repo: str,
    policies: list[BranchProtectionPolicy],
    branch: str | None = None,
    dry_run: bool = False,
) -> BranchProtectionSyncResult:
    """Synchronize declared branch protection policies to GitHub repository."""
    target_policies = [p for p in policies if branch is None or p.branch == branch]
    synced: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    with trace_span(
        "github.branch_protection.sync",
        attributes={"repo": repo, "dry_run": dry_run, "policies_count": len(target_policies)},
    ):
        for pol in target_policies:
            try:
                remote = get_remote_branch_protection(repo, pol.branch)
                diff = diff_branch_protection(pol, remote)
                if diff.is_compliant:
                    skipped.append(pol.branch)
                    continue

                if dry_run:
                    synced.append(pol.branch)
                    continue

                payload = build_protection_payload(pol)
                _apply_remote_protection(repo, pol.branch, payload)
                synced.append(pol.branch)
            except GitHubOperationError as exc:
                logger.error("Sync failed for branch %s: %s", pol.branch, exc)
                failed.append(pol.branch)

    return BranchProtectionSyncResult(
        synced_branches=synced,
        skipped_branches=skipped,
        failed_branches=failed,
        dry_run=dry_run,
    )
