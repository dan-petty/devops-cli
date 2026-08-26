"""GitHub API client integration, repository discovery, and SSH key management."""

from __future__ import annotations

from devops_cli.github.client import GitHubClient, RepoInfo
from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

__all__ = [
    "GitHubClient",
    "RepoInfo",
    "SSHRegistrationError",
    "register_key_on_github",
]
