"""GitHub API client integration, repository discovery, SSH key management, and project governance."""

from __future__ import annotations

from devops_cli.github.client import GitHubClient, RepoInfo
from devops_cli.github.labels import (
    LabelAuditFinding,
    LabelAuditResult,
    LabelSpec,
    LabelSyncResult,
    audit_repository_labels,
    diff_labels,
    load_label_specs,
    sync_repository_labels,
)
from devops_cli.github.milestones import (
    MilestoneProgress,
    MilestoneSpec,
    MilestoneSyncResult,
    calculate_milestone_progress,
    diff_milestones,
    extract_roadmap_milestones,
    sync_repository_milestones,
)
from devops_cli.github.projects import (
    ProjectField,
    ProjectFieldOption,
    ProjectItem,
    ProjectTemplate,
    ProjectView,
    load_project_template,
    parse_tasks_to_project_items,
)
from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

__all__ = [
    "GitHubClient",
    "LabelAuditFinding",
    "LabelAuditResult",
    "LabelSpec",
    "LabelSyncResult",
    "MilestoneProgress",
    "MilestoneSpec",
    "MilestoneSyncResult",
    "ProjectField",
    "ProjectFieldOption",
    "ProjectItem",
    "ProjectTemplate",
    "ProjectView",
    "RepoInfo",
    "SSHRegistrationError",
    "audit_repository_labels",
    "calculate_milestone_progress",
    "diff_labels",
    "diff_milestones",
    "extract_roadmap_milestones",
    "load_label_specs",
    "load_project_template",
    "parse_tasks_to_project_items",
    "register_key_on_github",
    "sync_repository_labels",
    "sync_repository_milestones",
]
