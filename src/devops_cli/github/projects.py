"""GitHub Projects v2 declarative template schemas, view definitions, and task tracking sync."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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
