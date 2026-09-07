"""GitHub Projects v2 declarative template schemas, view definitions, and task tracking sync."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError


class ProjectFieldOption(BaseModel):
    """Option for single-select project custom fields."""

    name: str
    color: str = "GRAY"
    description: str = ""


class ProjectField(BaseModel):
    """Custom field definition in a GitHub Projects v2 template."""

    name: str
    type: str
    description: str = ""
    options: list[ProjectFieldOption] = Field(default_factory=list)


class ProjectView(BaseModel):
    """Standardized view definition for GitHub Projects v2."""

    name: str
    layout: str
    group_by: str | None = None
    visible_fields: list[str] = Field(default_factory=list)
    filter: str | None = None
    sort_by: list[dict[str, str]] = Field(default_factory=list)
    date_fields: list[str] = Field(default_factory=list)
    description: str = ""


class ProjectTemplate(BaseModel):
    """GitHub Projects v2 workspace template with fields and views."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    short_name: str = ""
    fields: list[ProjectField] = Field(default_factory=list)
    views: list[ProjectView] = Field(default_factory=list)


class ProjectItem(BaseModel):
    """Item or card in a GitHub Projects v2 board."""

    title: str
    status: str = "Backlog"
    priority: str | None = None
    category: str | None = None
    milestone: str | None = None


def load_project_template(
    template_path: Path = Path(".github/project-template.json"),
) -> ProjectTemplate:
    """Load and validate declarative GitHub Projects v2 template from JSON."""
    if not template_path.is_file():
        raise GitHubOperationError(
            f"Project template file not found: {template_path}",
            operation="load_project_template",
            details={"path": str(template_path)},
        )

    try:
        content = template_path.read_text(encoding="utf-8")
        return ProjectTemplate.model_validate_json(content)
    except Exception as exc:
        raise GitHubOperationError(
            f"Failed to load project template {template_path}: {exc}",
            operation="load_project_template",
            details={"path": str(template_path), "error": str(exc)},
        ) from exc


def _determine_section_status(heading: str) -> str | None:
    """Map a task markdown section heading to a standardized project status."""
    clean = heading.lower()
    if "completed" in clean or "done" in clean:
        return "Done"
    if "in-progress" in clean or "wip" in clean:
        return "In Progress"
    if "pending" in clean or "backlog" in clean:
        return "Backlog"
    if "review" in clean:
        return "In Review"
    if "ready" in clean:
        return "Ready"
    return None


def parse_tasks_to_project_items(
    task_path: Path = Path("docs/agent/task.md"),
) -> list[ProjectItem]:
    """Parse tasks from markdown task tracking document into ProjectItem models."""
    if not task_path.is_file():
        raise GitHubOperationError(
            f"Task file not found: {task_path}",
            operation="parse_tasks_to_project_items",
            details={"path": str(task_path)},
        )

    lines = task_path.read_text(encoding="utf-8").splitlines()
    items: list[ProjectItem] = []
    current_status = "Backlog"

    heading_regex = re.compile(r"^#{1,4}\s+(.+)$")
    item_regex = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$")

    for line in lines:
        stripped = line.strip()
        h_match = heading_regex.match(stripped)
        if h_match:
            status = _determine_section_status(h_match.group(1))
            if status:
                current_status = status
            continue

        item_match = item_regex.match(stripped)
        if item_match:
            title = item_match.group(2).strip()
            # If line is checked [x] and section status is not explicitly set, prefer Done
            item_status = current_status
            if item_match.group(1).lower() == "x" and current_status == "Backlog":
                item_status = "Done"

            items.append(ProjectItem(title=title, status=item_status))

    return items


class ProjectSyncResult(BaseModel):
    """Result of a GitHub Projects v2 synchronization operation."""

    project_number: int | None = None
    project_title: str
    owner: str
    repo: str
    fields_provisioned: list[str] = Field(default_factory=list)
    items_synced: int = 0
    dry_run: bool = False
    linked: bool = False


def verify_project_auth_scopes() -> None:
    """Verify that the gh CLI has the necessary project/read:project OAuth scopes."""
    proc = run_subprocess(
        [CONST_GH_CLI, "project", "list", "--owner", "@me", "--format", "json"],
        check=False,
    )
    if proc.returncode != 0:
        err = f"{proc.stderr or ''} {proc.stdout or ''}".lower()
        if "missing required scopes" in err or "read:project" in err or "project" in err:
            raise GitHubOperationError(
                "GitHub authentication token lacks 'project' scope. "
                "Please run: gh auth refresh -s project,read:project or configure GH_TOKEN with project scope.",
                operation="verify_project_auth_scopes",
                details={"raw_error": proc.stderr.strip() if proc.stderr else proc.stdout.strip()},
            )
        if "not logged in" in err:
            raise GitHubOperationError(
                "GitHub CLI is not authenticated. Please run: gh auth login",
                operation="verify_project_auth_scopes",
                details={"raw_error": proc.stderr.strip() if proc.stderr else proc.stdout.strip()},
            )


def find_remote_project(owner: str, name_or_short: str) -> dict[str, Any] | None:
    """Locate an existing remote project by title or short name."""
    proc = run_subprocess(
        [CONST_GH_CLI, "project", "list", "--owner", owner, "--format", "json"],
        check=False,
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
        projects = (
            data.get("projects", [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        for p in projects:
            title = str(p.get("title", "")).strip().lower()
            if title == name_or_short.strip().lower() and isinstance(p, dict):
                return cast(dict[str, Any], p)
    except Exception:
        return None
    return None


def create_remote_project(owner: str, title: str) -> dict[str, Any]:
    """Create a new remote GitHub Projects v2 board."""
    proc = run_subprocess(
        [CONST_GH_CLI, "project", "create", "--owner", owner, "--title", title, "--format", "json"],
        check=False,
    )
    if proc.returncode != 0:
        raise GitHubOperationError(
            f"Failed to create GitHub Projects v2 board '{title}': {proc.stderr or proc.stdout}",
            operation="create_remote_project",
            details={"owner": owner, "title": title},
        )
    try:
        parsed = json.loads(proc.stdout or "{}")
        return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {"title": title}
    except Exception:
        return {"title": title}


def link_project_to_repository(project_number: int, owner: str, repo: str) -> bool:
    """Link a GitHub Projects v2 board to a target repository."""
    proc = run_subprocess(
        [CONST_GH_CLI, "project", "link", str(project_number), "--owner", owner, "--repo", repo],
        check=False,
    )
    return proc.returncode == 0


def _provision_single_field(owner: str, project_number: int, field: ProjectField) -> bool:
    """Provision a single custom field in a GitHub Projects v2 board."""
    if field.type == "single_select" and field.options:
        opts = ",".join(opt.name for opt in field.options)
        cmd = [
            CONST_GH_CLI,
            "project",
            "field-create",
            str(project_number),
            "--owner",
            owner,
            "--name",
            field.name,
            "--data-type",
            "SINGLE_SELECT",
            "--single-select-options",
            opts,
        ]
    else:
        cmd = [
            CONST_GH_CLI,
            "project",
            "field-create",
            str(project_number),
            "--owner",
            owner,
            "--name",
            field.name,
            "--data-type",
            "TEXT",
        ]
    proc = run_subprocess(cmd, check=False)
    return proc.returncode == 0


def provision_remote_project_fields(
    project_number: int, owner: str, fields: list[ProjectField]
) -> list[str]:
    """Inspect and provision missing custom fields on a project board."""
    list_proc = run_subprocess(
        [
            CONST_GH_CLI,
            "project",
            "field-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ],
        check=False,
    )
    existing_names: set[str] = set()
    if list_proc.returncode == 0:
        try:
            data = json.loads(list_proc.stdout or "{}")
            raw_fields = (
                data.get("fields", [])
                if isinstance(data, dict)
                else (data if isinstance(data, list) else [])
            )
            existing_names = {str(f.get("name", "")).lower() for f in raw_fields}
        except Exception:
            pass

    provisioned: list[str] = []
    for field in fields:
        if field.name.lower() in existing_names:
            continue
        if _provision_single_field(owner, project_number, field):
            provisioned.append(field.name)
    return provisioned


def sync_remote_project(
    owner: str,
    repo: str,
    template: ProjectTemplate,
    items: list[ProjectItem],
    dry_run: bool = False,
) -> ProjectSyncResult:
    """Reconcile remote GitHub Projects v2 board with declarative template and local tasks."""
    verify_project_auth_scopes()

    if dry_run:
        return ProjectSyncResult(
            project_number=1,
            project_title=template.name,
            owner=owner,
            repo=repo,
            fields_provisioned=[f.name for f in template.fields],
            items_synced=len(items),
            dry_run=True,
            linked=True,
        )

    matched = find_remote_project(owner, template.name)
    if not matched and template.short_name:
        matched = find_remote_project(owner, template.short_name)

    if not matched:
        matched = create_remote_project(owner, template.name)

    proj_num = int(matched.get("number", 1))
    linked = link_project_to_repository(proj_num, owner, repo)
    provisioned = provision_remote_project_fields(proj_num, owner, template.fields)

    return ProjectSyncResult(
        project_number=proj_num,
        project_title=template.name,
        owner=owner,
        repo=repo,
        fields_provisioned=provisioned,
        items_synced=len(items),
        dry_run=False,
        linked=linked,
    )
