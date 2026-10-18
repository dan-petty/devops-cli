"""A pull request's two branches, as GitHub's REST API describes them in `pulls/{number}`, and
whether the pull request is the release pull request (`release/vX.Y.Z` into the default branch).

`devops pr check-readiness` exempts the release pull request from grounding, and `devops pr
copilot-pass` requests a Copilot pass on it alone (#1345), so both read it here.
"""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import CONST_RELEASE_BRANCH_RE


def _repo_full_name(side: dict[str, Any]) -> str:
    """The `owner/repo` one side of a pull request lives in, lower-cased; empty when unknown."""
    repo = side.get("repo")
    return str(repo.get("full_name") or "").lower() if isinstance(repo, dict) else ""


def same_repository(pr_data: dict[str, Any]) -> bool:
    """Whether the PR's head lives in its base's repository rather than a fork."""
    head, base = pr_data.get("head") or {}, pr_data.get("base") or {}
    return _repo_full_name(head) != "" and _repo_full_name(head) == _repo_full_name(base)


def branch_ref(pr_data: dict[str, Any], side: str) -> str:
    """The branch name on one side (`head` or `base`) of a pull request."""
    return str((pr_data.get(side) or {}).get("ref") or "")


def default_branch(pr_data: dict[str, Any]) -> str:
    """The default branch of the PR's base repository; empty when unknown."""
    base = pr_data.get("base") or {}
    return str((base.get("repo") or {}).get("default_branch") or "")


def is_release_pr(pr_data: dict[str, Any]) -> bool:
    """Whether this is the release PR: `release/vX.Y.Z` into the default branch, not from a fork."""
    default = default_branch(pr_data)
    into_default = default != "" and branch_ref(pr_data, "base") == default
    release_head = CONST_RELEASE_BRANCH_RE.fullmatch(branch_ref(pr_data, "head")) is not None
    return same_repository(pr_data) and into_default and release_head


__all__ = ["branch_ref", "default_branch", "is_release_pr", "same_repository"]
