"""GitHub Projects v2 declarative template schemas, view definitions, and task tracking sync."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import (
    DEFAULT_GH_CACHE_TTL_SECONDS,
    DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD,
    DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC,
    DEFAULT_GH_PROJECT_OPTION_COLOR,
)
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.github.client import parse_paginated_json
from devops_cli.github.rate_limiter import (
    extract_json_payload,
    get_github_rate_limiter,
    run_gh,
)

logger = logging.getLogger(__name__)


class ProjectFieldOption(BaseModel):
    """Option for single-select project custom fields.

    `replaces` names board options this one takes the place of, for `devops roadmap migrate`.
    Its plan has a person rename the first one the board has to this option in the board's
    field settings, which keeps its id and so every card's value. Migrate moves the cards
    holding any other here, and then the person removes that option.
    """

    name: str
    color: str = DEFAULT_GH_PROJECT_OPTION_COLOR
    description: str = ""
    replaces: list[str] = Field(default_factory=list)


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


class MutationBudget:
    """Tracks and bounds the aggregate count of GraphQL write mutations across sync phases."""

    def __init__(self, limit: int = DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC) -> None:
        self.limit = max(0, limit)
        self.remaining = self.limit
        self.total_mutations = 0

    @property
    def is_exhausted(self) -> bool:
        """Return True if mutation budget has been reached or exceeded."""
        return self.remaining <= 0

    def record_mutation(self) -> bool:
        """Record a successful write mutation. Return True if permitted, False if exhausted."""
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        self.total_mutations += 1
        return True


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
    """Map a task markdown section heading to a standardized project status.

    Task files carry no review state: a project card takes `In Review` from the pull request
    that closes its issue (`plan_item_changes`), never from the file.
    """
    clean = heading.lower().replace("-", " ")
    if "completed" in clean or "done" in clean:
        return "Done"
    if "in progress" in clean or "wip" in clean:
        return "In Progress"
    if "pending" in clean or "backlog" in clean:
        return "Backlog"
    if "ready" in clean:
        return "Ready"
    return None


def _is_task_markdown(path: Path) -> bool:
    """Check whether path is an active task markdown file (excluding READMEs and archives)."""
    return (
        path.is_file()
        and not path.is_symlink()
        and path.name != "README.md"
        and "archive" not in path.parts
        and not path.name.startswith("archive")
    )


def _find_active_task_files_in_dir(task_dir: Path) -> list[Path]:
    """Find all active task markdown files in a directory, falling back to README.md if present."""
    active_files = [p for p in sorted(task_dir.glob("**/*.md")) if _is_task_markdown(p)]
    if active_files:
        return active_files
    readme = task_dir / "README.md"
    return [readme] if readme.is_file() and not readme.is_symlink() else []


def _resolve_default_task_fallbacks(task_path: Path) -> list[Path] | None:
    """Resolve standard fallback locations when default task path is requested."""
    if task_path != Path("docs/agent/tasks"):
        return None
    tasks_dir = Path("docs/agent/tasks")
    if tasks_dir.is_dir():
        files = _find_active_task_files_in_dir(tasks_dir)
        if files:
            return files
    return None


def _resolve_task_files(task_path: Path) -> list[Path]:
    """Resolve task_path (file or directory) to a list of existing markdown task files."""
    from devops_cli.core.paths import validate_no_path_traversal

    validate_no_path_traversal(task_path, label="Task path")
    if task_path.is_dir():
        return _find_active_task_files_in_dir(task_path)

    if task_path.is_file() and not task_path.is_symlink():
        return [task_path]

    fallback = _resolve_default_task_fallbacks(task_path)
    if fallback:
        return fallback

    raise GitHubOperationError(
        f"Task path not found: {task_path}",
        operation="parse_tasks_to_project_items",
        details={"path": str(task_path)},
    )


_HEADING_REGEX = re.compile(r"^#{1,4}\s+(.+)$")
_ITEM_REGEX = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$")
_STATUS_META_REGEX = re.compile(r"^(?:\*\*status\*\*|status)\s*:\s*(\w[\w\s-]+)", re.IGNORECASE)


def _extract_line_status(line: str) -> str | None:
    """Extract updated status from heading or metadata key in task markdown."""
    h_match = _HEADING_REGEX.match(line)
    if h_match:
        return _determine_section_status(h_match.group(1))
    s_match = _STATUS_META_REGEX.match(line)
    if s_match:
        return _determine_section_status(s_match.group(1))
    return None


def _parse_checklist_items(lines: list[str]) -> list[ProjectItem]:
    """Parse checkbox items from markdown lines with current section status."""
    items: list[ProjectItem] = []
    current_status = "Backlog"

    for line in lines:
        stripped = line.strip()
        status = _extract_line_status(stripped)
        if status:
            current_status = status
            continue

        item_match = _ITEM_REGEX.match(stripped)
        if item_match:
            title = item_match.group(2).strip()
            item_status = "Done" if item_match.group(1).lower() == "x" else current_status
            items.append(ProjectItem(title=title, status=item_status))

    return items


def _parse_standalone_task_metadata(lines: list[str]) -> ProjectItem | None:
    """Parse single task item from a markdown document without checklist items."""
    title: str | None = None
    file_status = "Backlog"

    for line in lines:
        stripped = line.strip()
        if not title:
            h_match = _HEADING_REGEX.match(stripped)
            if h_match and not any(
                kw in stripped.lower() for kw in ("readme", "tracking", "tasks")
            ):
                raw = h_match.group(1).strip()
                title = re.sub(r"^task:\s*", "", raw, flags=re.IGNORECASE)
        status_match = re.search(
            r"(?:status|\*\*status\*\*)\s*:\s*(\w[\w\s-]+)", stripped, re.IGNORECASE
        )
        if status_match:
            parsed_status = _determine_section_status(status_match.group(1))
            if parsed_status:
                file_status = parsed_status

    return ProjectItem(title=title, status=file_status) if title else None


def _parse_single_task_file(file_path: Path) -> list[ProjectItem]:
    """Parse tasks from a single markdown task document."""
    lines = file_path.read_text(encoding="utf-8").splitlines()
    items = _parse_checklist_items(lines)
    if items:
        return items
    standalone = _parse_standalone_task_metadata(lines)
    return [standalone] if standalone else []


def parse_tasks_to_project_items(
    task_path: Path = Path("docs/agent/tasks"),
) -> list[ProjectItem]:
    """Parse tasks from markdown task tracking directory or document into ProjectItem models."""
    resolved_files = _resolve_task_files(task_path)
    items: list[ProjectItem] = []
    for f in resolved_files:
        items.extend(_parse_single_task_file(f))
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


def check_github_rate_limit_error(output: str, operation: str = "github_operation") -> None:
    """Raise `GitHubRateLimitError` if subprocess output indicates a GitHub API rate limit exhaustion."""
    clean = output.lower()
    rate_limit_indicators = (
        "unknown owner type",
        "api rate limit already exceeded",
        "graphql_rate_limit",
        "rate limit exceeded",
    )
    if any(ind in clean for ind in rate_limit_indicators):
        raise GitHubRateLimitError(
            "GitHub API rate limit is currently exhausted. Please wait for quota reset.",
            operation=operation,
            details={"output": output.strip()},
        )


def verify_project_auth_scopes() -> None:
    """Verify that the gh CLI has the necessary project/read:project OAuth scopes."""
    proc = run_gh(
        [CONST_GH_CLI, "project", "list", "--owner", "@me", "--format", "json"],
        check=False,
    )
    if proc.returncode != 0:
        err = f"{proc.stderr or ''} {proc.stdout or ''}".lower()
        check_github_rate_limit_error(err, operation="verify_project_auth_scopes")
        scope_error_patterns = (
            "missing required scopes",
            "insufficient_scopes",
            "read:project",
            "scope 'project'",
            'scope "project"',
            "project scope",
            "oauth scope",
            "requires additional permissions",
            "requires the 'project' scope",
            "need the 'project' scope",
        )
        if any(pattern in err for pattern in scope_error_patterns):
            raise GitHubOperationError(
                "GitHub authentication token lacks 'project' scope. "
                "Please run: gh auth refresh -s project,read:project or configure GH_TOKEN with project scope.",
                operation="verify_project_auth_scopes",
                details={"raw_error": proc.stderr.strip() if proc.stderr else proc.stdout.strip()},
            )
        if "not logged in" in err or "authentication required" in err:
            raise GitHubOperationError(
                "GitHub CLI is not authenticated. Please run: gh auth login",
                operation="verify_project_auth_scopes",
                details={"raw_error": proc.stderr.strip() if proc.stderr else proc.stdout.strip()},
            )


def _find_project_in_list(projects: list[Any], target: str) -> dict[str, Any] | None:
    """Find a project by matching lowercased title."""
    clean_target = target.strip().lower()
    for p in projects:
        if isinstance(p, dict) and str(p.get("title", "")).strip().lower() == clean_target:
            return cast(dict[str, Any], p)
    return None


def _find_project_via_rest(owner: str, name_or_short: str) -> dict[str, Any] | None:
    """Attempt to locate a remote project via GitHub REST API."""
    for endpoint in (f"users/{owner}/projectsV2", f"orgs/{owner}/projectsV2"):
        cmd = [CONST_GH_CLI, "api", endpoint, "-H", "Accept: application/vnd.github+json"]
        proc = run_gh(cmd, check=False, quiet=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        data = extract_json_payload(proc.stdout)
        if isinstance(data, list):
            match = _find_project_in_list(data, name_or_short)
            if match:
                return match
    return None


_CURRENT_USER_CACHE: str | None = None
_PROJECT_OWNER_ARG_CACHE: dict[str, str] = {}


def _get_authenticated_user() -> str | None:
    """Retrieve the username of the currently authenticated GitHub CLI user."""
    global _CURRENT_USER_CACHE
    if _CURRENT_USER_CACHE is not None:
        return _CURRENT_USER_CACHE
    proc = run_gh([CONST_GH_CLI, "api", "user", "--jq", ".login"], check=False, quiet=True)
    if proc.returncode == 0 and proc.stdout.strip():
        _CURRENT_USER_CACHE = proc.stdout.strip().lower()
        return _CURRENT_USER_CACHE
    return None


def _resolve_project_owner_arg(owner: str) -> str:
    """Normalize owner argument for gh project CLI commands without hardcoding usernames."""
    clean_owner = owner.strip()
    if clean_owner == "@me":
        return "@me"
    if clean_owner in _PROJECT_OWNER_ARG_CACHE:
        return _PROJECT_OWNER_ARG_CACHE[clean_owner]
    current_user = _get_authenticated_user()
    if current_user and clean_owner.lower() == current_user:
        return "@me"
    return clean_owner


def _run_project_cli(
    cmd: list[str], owner_arg: str, check: bool = False, quiet: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute a gh project CLI command with automated @me fallback on unknown owner type."""
    proc = run_gh(cmd, check=check, quiet=quiet)
    if proc.returncode == 0 or owner_arg == "@me":
        return proc
    err_output = f"{proc.stderr or ''} {proc.stdout or ''}".lower()
    if "unknown owner type" in err_output and "--owner" in cmd:
        fallback_cmd = list(cmd)
        owner_idx = fallback_cmd.index("--owner") + 1
        if owner_idx < len(fallback_cmd):
            fallback_cmd[owner_idx] = "@me"
            fallback_proc = run_gh(fallback_cmd, check=check, quiet=quiet)
            if fallback_proc.returncode == 0:
                _PROJECT_OWNER_ARG_CACHE[owner_arg] = "@me"
            return fallback_proc
    return proc


def _find_project_via_cli(owner: str, name_or_short: str) -> dict[str, Any] | None:
    """Fallback to searching projects via gh project list CLI."""
    owner_arg = _resolve_project_owner_arg(owner)
    proc = _run_project_cli(
        [CONST_GH_CLI, "project", "list", "--owner", owner_arg, "--format", "json"],
        owner_arg=owner_arg,
    )
    if proc.returncode != 0:
        err = f"{proc.stderr or ''} {proc.stdout or ''}"
        check_github_rate_limit_error(err, operation="find_remote_project")
        return None
    data = extract_json_payload(proc.stdout)
    projects = (
        data.get("projects", [])
        if isinstance(data, dict)
        else (data if isinstance(data, list) else [])
    )
    return _find_project_in_list(projects, name_or_short)


def _find_project_via_repo(owner: str, repo: str, name_or_short: str) -> dict[str, Any] | None:
    """Locate an existing remote project linked to the target repository."""
    clean_repo = repo.split("/")[-1] if "/" in repo else repo
    clean_owner = owner.split("/")[0] if "/" in owner else owner
    query = (
        "query($owner: String!, $repo: String!) { "
        "repository(owner: $owner, name: $repo) { "
        "projectsV2(first: 20) { nodes { number title id url } } } }"
    )
    proc = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={clean_owner}",
            "-F",
            f"repo={clean_repo}",
        ],
        check=False,
        quiet=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    data = extract_json_payload(proc.stdout)
    if not isinstance(data, dict):
        return None
    nodes = data.get("data", {}).get("repository", {}).get("projectsV2", {}).get("nodes", [])
    return _find_project_in_list(nodes, name_or_short) if isinstance(nodes, list) else None


def find_remote_project(
    owner: str, name_or_short: str, repo: str | None = None
) -> dict[str, Any] | None:
    """Locate an existing remote project by title or short name, checking linked repository first."""
    if repo:
        matched = _find_project_via_repo(owner, repo, name_or_short)
        if matched:
            return matched
    return _find_project_via_rest(owner, name_or_short) or _find_project_via_cli(
        owner, name_or_short
    )


def create_remote_project(owner: str, title: str) -> dict[str, Any]:
    """Create a new remote GitHub Projects v2 board."""
    current_user = _get_authenticated_user()
    if current_user and "github-actions" in current_user:
        raise GitHubOperationError(
            f"GitHub Actions runner ('{current_user}') does not have permission to create user-owned Projects v2 "
            f"boards for '{owner}'. Please link the project to the repository or configure repository secret "
            "'PROJECT_TOKEN' with a Personal Access Token having 'project' and 'repo' scopes.",
            operation="create_remote_project",
            details={"owner": owner, "title": title},
        )
    owner_arg = _resolve_project_owner_arg(owner)
    proc = _run_project_cli(
        [
            CONST_GH_CLI,
            "project",
            "create",
            "--owner",
            owner_arg,
            "--title",
            title,
            "--format",
            "json",
        ],
        owner_arg=owner_arg,
    )
    if proc.returncode != 0:
        raise GitHubOperationError(
            f"Failed to create GitHub Projects v2 board '{title}': {proc.stderr or proc.stdout}",
            operation="create_remote_project",
            details={"owner": owner, "title": title},
        )
    parsed = extract_json_payload(proc.stdout)
    return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {"title": title}


def link_project_to_repository(project_number: int, owner: str, repo: str) -> bool:
    """Link a GitHub Projects v2 board to a target repository."""
    clean_owner = owner.strip()
    if clean_owner == "@me":
        current_user = _get_authenticated_user()
        clean_owner = current_user or "@me"
    clean_repo_name = repo.split("/")[-1] if "/" in repo else repo
    full_repo = f"{clean_owner}/{clean_repo_name}"
    proc = run_gh(
        [
            CONST_GH_CLI,
            "project",
            "link",
            str(project_number),
            "--owner",
            clean_owner,
            "--repo",
            full_repo,
        ],
        check=False,
        quiet=True,
    )
    return proc.returncode == 0


def _fetch_project_workflow_nodes(proj_id: str) -> list[dict[str, Any]]:
    """Query raw ProjectV2 workflow nodes via GraphQL."""
    query = (
        "query($id: ID!) { "
        "node(id: $id) { "
        "... on ProjectV2 { "
        "workflows(first: 20) { "
        "nodes { id name number enabled } } } } }"
    )
    proc = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"id={proj_id}",
        ],
        check=False,
        quiet=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    data = extract_json_payload(proc.stdout)
    if not isinstance(data, dict):
        return []
    nodes = data.get("data", {}).get("node", {}).get("workflows", {}).get("nodes", [])
    return [w for w in nodes if isinstance(w, dict)] if isinstance(nodes, list) else []


def get_project_workflows(
    project_number: int,
    owner: str,
    repo: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve built-in ProjectV2 workflows and automation states."""
    proj = find_remote_project(owner, str(project_number), repo=repo)
    if not proj:
        proj_list = list_remote_projects(owner)
        proj = next((p for p in proj_list if p.get("number") == project_number), None)
    if not proj:
        return []
    proj_id = proj.get("id") or proj.get("node_id")
    if not proj_id:
        return []

    nodes = _fetch_project_workflow_nodes(str(proj_id))
    clean_owner = owner.split("/")[0] if "/" in owner else owner
    base_url = f"https://github.com/users/{clean_owner}/projects/{project_number}/workflows"
    return [
        {
            "id": w.get("id", ""),
            "name": w.get("name", ""),
            "number": w.get("number", 0),
            "enabled": bool(w.get("enabled", False)),
            "url": f"{base_url}/{w.get('number')}" if w.get("number") else base_url,
        }
        for w in nodes
    ]


def _provision_single_field(owner: str, project_number: int, field: ProjectField) -> bool:
    """Provision a single custom field in a GitHub Projects v2 board."""
    owner_arg = _resolve_project_owner_arg(owner)
    cmd = [
        CONST_GH_CLI,
        "project",
        "field-create",
        str(project_number),
        "--owner",
        owner_arg,
        "--name",
        field.name,
    ]
    if field.type == "single_select" and field.options:
        opts = ",".join(opt.name for opt in field.options)
        cmd.extend(["--data-type", "SINGLE_SELECT", "--single-select-options", opts])
    else:
        cmd.extend(["--data-type", "TEXT"])
    proc = _run_project_cli(cmd, owner_arg=owner_arg)
    return proc.returncode == 0


def _fetch_existing_fields_by_name(
    owner_arg: str, project_number: int
) -> dict[str, dict[str, Any]]:
    """Retrieve existing fields indexed by lowercase name."""
    list_proc = _run_project_cli(
        [
            CONST_GH_CLI,
            "project",
            "field-list",
            str(project_number),
            "--owner",
            owner_arg,
            "--format",
            "json",
        ],
        owner_arg=owner_arg,
    )
    if list_proc.returncode != 0 or not list_proc.stdout.strip():
        return {}
    data = extract_json_payload(list_proc.stdout)
    raw_fields = (
        data.get("fields", [])
        if isinstance(data, dict)
        else (data if isinstance(data, list) else [])
    )
    return {
        str(rf["name"]).lower(): rf for rf in raw_fields if isinstance(rf, dict) and "name" in rf
    }


def provision_remote_project_fields(
    project_number: int, owner: str, fields: list[ProjectField]
) -> list[str]:
    """Create the template fields the board lacks, and never edit an existing field's options.

    GitHub replaces a single-select field's whole option list, and its option input takes no
    id, so every option it is sent gets a new id and every card loses its value. No command
    edits an existing board's options: `devops roadmap migrate` lists the edits a person makes
    in the board's field settings, which keep ids.
    """
    owner_arg = _resolve_project_owner_arg(owner)
    existing_fields_by_name = _fetch_existing_fields_by_name(owner_arg, project_number)
    missing = [field for field in fields if field.name.lower() not in existing_fields_by_name]
    return [
        field.name for field in missing if _provision_single_field(owner_arg, project_number, field)
    ]


def _extract_item_url(it: dict[str, Any]) -> str | None:
    """Extract canonical URL from a project item representation."""
    content = it.get("content") or {}
    return content.get("url") or content.get("html_url") or it.get("url") or it.get("html_url")


def _normalize_field_value(raw: Any) -> str | None:
    """Normalize raw field value to string or None."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return str(raw.get("name") or raw.get("title") or "")
    return str(raw)


def _extract_item_fields(it: dict[str, Any]) -> dict[str, str | None]:
    """Extract custom field mapping from project item, handling case variance."""
    fields_by_lower = {str(k).lower(): _normalize_field_value(v) for k, v in it.items()}
    return {
        "status": fields_by_lower.get("status"),
        "priority": fields_by_lower.get("priority"),
        "value": fields_by_lower.get("value"),
        "effort": fields_by_lower.get("effort"),
        "id": fields_by_lower.get("id"),
    }


def _parse_project_items_json(stdout: str) -> dict[str, dict[str, str | None]]:
    """Parse output of gh project item-list or REST items into mapping of URL -> {field: value}."""
    if not stdout or not stdout.strip():
        return {}
    payload = extract_json_payload(stdout)
    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return {}
    items_data: dict[str, dict[str, str | None]] = {}
    for it in raw_items:
        if isinstance(it, dict):
            url = _extract_item_url(it)
            if url:
                items_data[url] = _extract_item_fields(it)
    return items_data


def _fetch_project_items_data(owner: str, project_number: int) -> dict[str, dict[str, str | None]]:
    """Retrieve items and current custom field values from the project board.

    Raises when the board cannot be read, so a failed read never looks like an empty board.
    """
    owner_arg = _resolve_project_owner_arg(owner)
    cmd = [
        CONST_GH_CLI,
        "project",
        "item-list",
        str(project_number),
        "--owner",
        owner_arg,
        "--format",
        "json",
        "--limit",
        "1000",
    ]
    proc = run_gh(cmd, check=False, quiet=True, use_cache=True, cache_ttl=60.0)
    if proc.returncode != 0 and owner_arg != "@me":
        fallback_cmd = [
            CONST_GH_CLI,
            "project",
            "item-list",
            str(project_number),
            "--owner",
            "@me",
            "--format",
            "json",
            "--limit",
            "1000",
        ]
        proc = run_gh(fallback_cmd, check=False, quiet=True, use_cache=True, cache_ttl=60.0)

    if proc.returncode == 0:
        return _parse_project_items_json(proc.stdout or "")

    err_output = f"{proc.stderr or ''} {proc.stdout or ''}".strip()
    check_github_rate_limit_error(err_output, operation="fetch_project_items")
    raise GitHubOperationError(
        f"Failed to read project #{project_number} items (exit {proc.returncode}): {err_output[:256]}",
        operation="fetch_project_items",
        details={"project_number": project_number},
    )


def _fetch_repository_list(repo: str, kind: str, state: str) -> list[dict[str, Any]]:
    """Fetch every page of a repository's issues or pull requests, raising if GitHub can't be read."""
    res = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "--paginate",
            f"repos/{repo}/{kind}?state={state}&per_page=100",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        check=False,
        quiet=True,
        use_cache=True,
        cache_ttl=DEFAULT_GH_CACHE_TTL_SECONDS,
    )
    if res.returncode != 0:
        err_output = f"{res.stderr or ''} {res.stdout or ''}".strip()
        check_github_rate_limit_error(err_output, operation=f"fetch_{kind}")
        raise GitHubOperationError(
            f"Failed to read {kind} for {repo} (exit {res.returncode}): {err_output[:256]}",
            operation=f"fetch_{kind}",
            details={"repo": repo, "state": state},
        )
    return parse_paginated_json(res.stdout or "")


def _fetch_repository_issues(repo: str, state: str = "open") -> list[dict[str, Any]]:
    """Retrieve candidate issues from the repository via GitHub API.

    The issues endpoint also returns pull requests, without their merge state; those come
    from the pulls endpoint instead, so each pull request is reconciled once.
    """
    return [it for it in _fetch_repository_list(repo, "issues", state) if "pull_request" not in it]


def _add_project_item_with_fallback(
    owner_arg: str,
    project_number: int,
    url: str,
) -> bool:
    """Add item to project via CLI with owner fallback."""
    cmd = [
        CONST_GH_CLI,
        "project",
        "item-add",
        str(project_number),
        "--owner",
        owner_arg,
        "--url",
        url,
    ]
    proc = _run_project_cli(cmd, owner_arg=owner_arg)
    return proc.returncode == 0


def _sync_single_issue_item(
    owner_arg: str,
    project_number: int,
    iss: dict[str, Any],
    existing_urls: set[str],
    budget: MutationBudget,
) -> bool:
    """Add a single issue to project if not already present."""
    url = iss.get("html_url") or iss.get("url")
    if not url or url in existing_urls:
        return False
    if _add_project_item_with_fallback(owner_arg, project_number, url):
        existing_urls.add(url)
        budget.record_mutation()
        return True
    return False


def sync_repository_issues_to_project(
    owner: str,
    repo: str,
    project_number: int,
    dry_run: bool = False,
    state: str = "open",
    budget: MutationBudget | None = None,
) -> int:
    """Synchronize open and active repository issues to the project board."""
    if dry_run or _is_graphql_quota_exhausted():
        return 0

    mutation_budget = budget or MutationBudget(limit=DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC)
    owner_arg = _resolve_project_owner_arg(owner)
    existing_items = _fetch_project_items_data(owner, project_number)
    existing_urls = set(existing_items.keys())
    issues = _fetch_repository_issues(repo, state=state)
    added = 0

    for iss in issues:
        if mutation_budget.is_exhausted or _is_graphql_quota_exhausted():
            logger.warning(
                "GraphQL quota critically low or reached mutation budget. Halting issue sync."
            )
            break
        if _sync_single_issue_item(owner_arg, project_number, iss, existing_urls, mutation_budget):
            added += 1

    return added


class FieldChange(BaseModel):
    """One board field change that reconcile plans or makes, and what decided it."""

    url: str
    field: str
    old: str | None
    new: str
    source: str


# Labels match exactly: `status/ready-to-merge` is not `status/ready`.
_STATUS_LABELS: dict[str, str] = {
    "status/backlog": "New",
    "status/ready": "Ready",
    "status/in-progress": "In Progress",
    "status/in-review": "In Review",
    "status/blocked": "Blocked",
}
_PRIORITY_LABELS: dict[str, str] = {
    "priority/p0-critical": "P0-Critical",
    "priority/p1-high": "P1-High",
    "priority/p2-medium": "P2-Medium",
    "priority/p3-low": "P3-Low",
}
_DEFAULT_STATUS = "New"


def _label_names(labels: Sequence[Any]) -> list[str]:
    """Return the lower-cased names of an item's labels."""
    return [
        str(lbl.get("name", "") if isinstance(lbl, dict) else lbl).lower() for lbl in labels or []
    ]


def _forced_status(item: Mapping[str, Any], has_open_pr: bool) -> tuple[str, str] | None:
    """Return the status an item's state forces, with its source, or None."""
    url = str(item.get("html_url") or item.get("url") or "")
    is_pr = "/pull/" in url or "pull_request" in item
    if str(item.get("state", "OPEN")).upper() in ("CLOSED", "MERGED"):
        if not is_pr:
            return "Done", "issue closed"
        return "Done", "pull request merged" if item.get("merged_at") else "pull request closed"
    if is_pr:
        if item.get("draft"):
            return "In Progress", "draft pull request"
        return "In Review", "open pull request"
    if has_open_pr:
        return "In Review", "linked open pull request"
    return None


def initial_status(labels: Sequence[Any], status_options: Collection[str]) -> tuple[str, str]:
    """Return the status for an item whose Status is unset, with its source."""
    for name in _label_names(labels):
        status = _STATUS_LABELS.get(name)
        if status is not None and status in status_options:
            return status, f"label {name}"
    return _DEFAULT_STATUS, "default for an unset status"


def declared_priority(labels: Sequence[Any]) -> tuple[str, str] | None:
    """Return the priority a priority label declares, with its source, or None."""
    for name in _label_names(labels):
        priority = _PRIORITY_LABELS.get(name)
        if priority is not None:
            return priority, f"label {name}"
    return None


def plan_item_changes(
    item: Mapping[str, Any],
    current: Mapping[str, str | None],
    *,
    has_open_pr: bool = False,
    status_options: Collection[str] = (),
) -> list[FieldChange]:
    """Plan one item's board field changes, each with the source that decided it.

    The board owns Status: it is set only when unset, or when the item's state forces Done,
    In Review or In Progress, so a person's triage is never reverted. Priority only fills an
    unset field, from a priority label. Value and Effort are never inferred: an inferred value
    the board shows as decided is worse than an unset one. The board mirrors the milestone on
    its own, so it is never written.
    """
    labels = item.get("labels", [])
    status = _forced_status(item, has_open_pr)
    if status is None and not current.get("status"):
        status = initial_status(labels, status_options)
    priority = None if current.get("priority") else declared_priority(labels)

    targets = (("Status", status), ("Priority", priority))
    url = str(item.get("html_url") or item.get("url") or "")
    changes: list[FieldChange] = []
    for field_name, target in targets:
        if target is None:
            continue
        new, source = target
        old = current.get(field_name.lower()) or None
        if old is None or old.strip().lower() != new.strip().lower():
            changes.append(FieldChange(url=url, field=field_name, old=old, new=new, source=source))
    return changes


def _fetch_repository_prs(repo: str, state: str = "open") -> list[dict[str, Any]]:
    """Retrieve candidate PRs from the repository via GitHub API."""
    return _fetch_repository_list(repo, "pulls", state)


def _edit_project_item_field(
    owner: str, project_number: int, url: str, field_name: str, field_val: str
) -> bool:
    """Update a single custom field value on a project item."""
    owner_arg = _resolve_project_owner_arg(owner)
    edit_cmd = [
        CONST_GH_CLI,
        "project",
        "item-edit",
        str(project_number),
        "--owner",
        owner_arg,
        "--url",
        url,
        "--field",
        field_name,
        "--value",
        field_val,
    ]
    proc = _run_project_cli(edit_cmd, owner_arg=owner_arg, check=False, quiet=True)
    return proc.returncode == 0


def _reconcile_single_item(
    owner: str,
    project_number: int,
    item: dict[str, Any],
    dry_run: bool,
    has_open_pr: bool = False,
    current_fields: Mapping[str, str | None] | None = None,
    budget: MutationBudget | None = None,
    status_options: Collection[str] = (),
) -> list[FieldChange]:
    """Plan an item's field changes and, unless dry-running, apply them.

    Returns the planned changes in a dry run, and the changes actually applied otherwise.
    """
    if not (item.get("html_url") or item.get("url")):
        return []
    changes = plan_item_changes(
        item,
        current_fields or {},
        has_open_pr=has_open_pr,
        status_options=status_options,
    )
    if dry_run or not changes:
        return changes
    return _apply_field_updates(owner, project_number, changes, current_fields, budget=budget)


def _apply_field_updates(
    owner: str,
    project_number: int,
    changes: list[FieldChange],
    current_fields: Mapping[str, str | None] | None,
    budget: MutationBudget | None = None,
) -> list[FieldChange]:
    """Apply field changes via gh project CLI, stopping early if quota runs out."""
    applied: list[FieldChange] = []
    for change in changes:
        if (budget is not None and budget.is_exhausted) or _is_graphql_quota_exhausted():
            logger.warning(
                "GraphQL quota critically low or reached mutation budget. Halting field update."
            )
            break
        if _edit_project_item_field(owner, project_number, change.url, change.field, change.new):
            applied.append(change)
            if budget is not None:
                budget.record_mutation()
            if isinstance(current_fields, dict):
                current_fields[change.field.lower()] = change.new
    return applied


def _extract_linked_issue_numbers(prs: list[dict[str, Any]]) -> set[int]:
    """Extract linked issue numbers from open pull requests."""
    linked_numbers: set[int] = set()
    keyword_pattern = re.compile(
        r"(?:closes|close|closed|fixes|fix|fixed|resolves|resolve|resolved)\s+#(\d+)",
        re.IGNORECASE,
    )
    title_pattern = re.compile(r"\(#(\d+)\)\s*$", re.IGNORECASE)

    for pr in prs:
        if str(pr.get("state", "")).upper() != "OPEN":
            continue
        text = f"{pr.get('title', '')} {pr.get('body', '')}"
        for match in keyword_pattern.finditer(text):
            if match.group(1).isdigit():
                linked_numbers.add(int(match.group(1)))
        for match in title_pattern.finditer(str(pr.get("title", ""))):
            if match.group(1).isdigit():
                linked_numbers.add(int(match.group(1)))

    return linked_numbers


def _is_graphql_quota_exhausted(
    threshold: int = DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD,
) -> bool:
    """Check if the tracked GraphQL quota is below safety threshold or unknown."""
    limiter = get_github_rate_limiter()
    quota = limiter.get_quota("graphql")
    if quota.remaining is None or not quota.is_valid():
        return True
    return quota.remaining < threshold


def _provision_missing_candidates(
    owner: str,
    project_number: int,
    candidates: list[dict[str, Any]],
    items_data: dict[str, dict[str, str | None]],
    budget: MutationBudget | None = None,
) -> None:
    """Add any missing candidate issues/PRs to the remote project board."""
    owner_arg = _resolve_project_owner_arg(owner)
    existing_urls = set(items_data.keys())
    mutation_budget = budget or MutationBudget(limit=DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC)
    for it in candidates:
        if mutation_budget.is_exhausted or _is_graphql_quota_exhausted():
            logger.warning(
                "GraphQL quota critically low or reached mutation budget. Halting candidate provisioning."
            )
            break
        url = it.get("html_url") or it.get("url")
        if (
            url
            and url not in existing_urls
            and _add_project_item_with_fallback(owner_arg, project_number, url)
        ):
            existing_urls.add(url)
            items_data[url] = {}
            mutation_budget.record_mutation()


def _can_continue_reconciliation(
    dry_run: bool,
    budget: MutationBudget | None = None,
) -> bool:
    """Predicate determining if candidate reconciliation may continue."""
    if dry_run:
        return True
    if _is_graphql_quota_exhausted():
        logger.warning("GraphQL quota critically low or unknown. Halting candidate reconciliation.")
        return False
    if budget is not None and budget.is_exhausted:
        logger.info(
            "Reached maximum mutations per sync budget (%d). Pausing reconciliation.",
            budget.limit,
        )
        return False
    return True


def _reconcile_candidate_items(
    owner: str,
    project_number: int,
    candidates: list[dict[str, Any]],
    items_data: dict[str, dict[str, str | None]],
    open_pr_issue_numbers: set[int],
    dry_run: bool,
    budget: MutationBudget | None = None,
    status_options: Collection[str] = (),
) -> list[FieldChange]:
    """Reconcile each candidate's fields, returning every change planned or applied."""
    changes: list[FieldChange] = []
    for it in candidates:
        if not _can_continue_reconciliation(dry_run, budget=budget):
            break
        url = it.get("html_url") or it.get("url") or ""
        if dry_run and url not in items_data:
            continue
        changes.extend(
            _reconcile_single_item(
                owner,
                project_number,
                it,
                dry_run,
                has_open_pr=(int(it.get("number", 0)) in open_pr_issue_numbers),
                current_fields=items_data.get(url),
                budget=budget,
                status_options=status_options,
            )
        )
    return changes


def _status_options(template: ProjectTemplate) -> list[str]:
    """Return the Status options a project template declares."""
    return [opt.name for fld in template.fields if fld.name == "Status" for opt in fld.options]


def reconcile_project_custom_fields(
    owner: str,
    repo: str,
    project_number: int,
    dry_run: bool = False,
    state: str = "open",
    budget: MutationBudget | None = None,
    template: ProjectTemplate | None = None,
) -> dict[str, Any]:
    """Reconcile Status and Priority on project items, listing every change.

    The result's ``changes`` holds each field change with its old and new value and the
    source that decided it: the planned changes in a dry run, the applied ones otherwise.
    """
    result: dict[str, Any] = {
        "project_number": project_number,
        "owner": owner,
        "repo": repo,
        "items_evaluated": 0,
        "items_reconciled": 0,
        "dry_run": dry_run,
        "changes": [],
    }
    if _is_graphql_quota_exhausted():
        logger.warning(
            "GraphQL quota critically low or unknown. Skipping project custom field reconciliation."
        )
        return result

    status_options = _status_options(template or load_project_template())
    active_items = _fetch_project_items_data(owner, project_number)
    mutation_budget = budget or MutationBudget(limit=DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC)
    issues = _fetch_repository_issues(repo, state=state)
    prs = _fetch_repository_prs(repo, state=state)
    candidates = issues + prs

    if not dry_run:
        _provision_missing_candidates(
            owner, project_number, candidates, active_items, budget=mutation_budget
        )

    eval_candidates = (
        [it for it in candidates if (it.get("html_url") or it.get("url") or "") in active_items]
        if dry_run
        else candidates
    )
    changes = _reconcile_candidate_items(
        owner,
        project_number,
        eval_candidates,
        active_items,
        _extract_linked_issue_numbers(prs),
        dry_run,
        budget=mutation_budget,
        status_options=status_options,
    )
    result.update(
        items_evaluated=len(eval_candidates),
        items_reconciled=len({change.url for change in changes}),
        changes=[change.model_dump() for change in changes],
    )
    return result


def sync_remote_project(
    owner: str,
    repo: str,
    template: ProjectTemplate,
    items: list[ProjectItem],
    dry_run: bool = False,
    reconcile_fields: bool = True,
) -> ProjectSyncResult:
    """Reconcile remote GitHub Projects v2 board with declarative template and local tasks."""
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

    verify_project_auth_scopes()

    matched = find_remote_project(owner, template.name, repo=repo)
    if not matched and template.short_name:
        matched = find_remote_project(owner, template.short_name, repo=repo)

    if not matched:
        matched = create_remote_project(owner, template.name)

    proj_num = int(matched.get("number", 1))
    linked = link_project_to_repository(proj_num, owner, repo)
    provisioned = provision_remote_project_fields(proj_num, owner, template.fields)
    mutation_budget = MutationBudget(limit=DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC)
    items_added = sync_repository_issues_to_project(
        owner, repo, proj_num, dry_run=False, budget=mutation_budget
    )
    if reconcile_fields:
        reconcile_project_custom_fields(
            owner, repo, proj_num, dry_run=False, budget=mutation_budget, template=template
        )

    return ProjectSyncResult(
        project_number=proj_num,
        project_title=template.name,
        owner=owner,
        repo=repo,
        fields_provisioned=provisioned,
        items_synced=len(items) + items_added,
        dry_run=False,
        linked=linked,
    )


def _map_view_layout(layout: str) -> str:
    """Map template layout string to GraphQL ProjectV2ViewLayout enum."""
    cleaned = layout.strip().lower()
    if "board" in cleaned:
        return "BOARD_LAYOUT"
    if "roadmap" in cleaned:
        return "ROADMAP_LAYOUT"
    return "TABLE_LAYOUT"


def get_remote_project_views(
    owner: str, repo: str
) -> tuple[str | None, int | None, list[dict[str, str]]]:
    """Fetch remote ProjectV2 ID, number, and views for the given repository."""
    repo_clean = repo.split("/")[-1]
    query = (
        f"query {{ repository(owner: {json.dumps(owner)}, name: {json.dumps(repo_clean)}) {{ "
        f"projectsV2(first: 5) {{ nodes {{ id number title views(first: 20) {{ nodes {{ id name layout }} }} }} }} }} }}"
    )
    cmd = [CONST_GH_CLI, "api", "graphql", "-f", f"query={query}"]
    proc = run_gh(cmd, check=False, quiet=True)
    if proc.returncode != 0 or not proc.stdout:
        return None, None, []
    data = extract_json_payload(proc.stdout)
    if not isinstance(data, dict):
        return None, None, []
    nodes = data.get("data", {}).get("repository", {}).get("projectsV2", {}).get("nodes", [])
    if not nodes:
        return None, None, []
    proj = nodes[0]
    views: list[dict[str, str]] = proj.get("views", {}).get("nodes", [])
    return proj.get("id"), proj.get("number"), views


def _create_project_view(project_id: str, name: str, layout: str) -> bool:
    """Create a project view via GraphQL mutation."""
    layout_enum = _map_view_layout(layout)
    mutation = (
        f"mutation {{ createProjectV2View(input: {{ projectId: {json.dumps(project_id)}, "
        f"name: {json.dumps(name)}, layout: {layout_enum} }}) {{ projectV2View {{ id name }} }} }}"
    )
    proc = run_gh(
        [CONST_GH_CLI, "api", "graphql", "-f", f"query={mutation}"],
        check=False,
        quiet=True,
    )
    return proc.returncode == 0


def _rename_default_view(view_id: str, name: str, layout: str) -> bool:
    """Rename default View 1 via GraphQL mutation."""
    layout_enum = _map_view_layout(layout)
    mutation = (
        f"mutation {{ updateProjectV2View(input: {{ viewId: {json.dumps(view_id)}, "
        f"name: {json.dumps(name)}, layout: {layout_enum} }}) {{ projectV2View {{ id name }} }} }}"
    )
    proc = run_gh(
        [CONST_GH_CLI, "api", "graphql", "-f", f"query={mutation}"],
        check=False,
        quiet=True,
    )
    return proc.returncode == 0


def sync_remote_project_views(owner: str, repo: str, template: ProjectTemplate) -> dict[str, Any]:
    """Reconcile template views against the remote GitHub Projects v2 board."""
    verify_project_auth_scopes()
    proj_id, proj_num, existing_views = get_remote_project_views(owner, repo)
    if not proj_id:
        return {
            "project_number": None,
            "created": [],
            "existing": [],
            "status": "No linked project found on repository",
        }

    existing_by_name = {v.get("name", "").lower(): v for v in existing_views}
    created: list[str] = []
    existing: list[str] = []

    for tv in template.views:
        if tv.name.lower() in existing_by_name:
            existing.append(tv.name)
            continue

        if "view 1" in existing_by_name and not created and not existing:
            view1_id = existing_by_name["view 1"].get("id", "")
            if _rename_default_view(view1_id, tv.name, tv.layout):
                created.append(tv.name)
                del existing_by_name["view 1"]
                continue

        if _create_project_view(proj_id, tv.name, tv.layout):
            created.append(tv.name)

    return {
        "project_number": proj_num,
        "created": created,
        "existing": existing,
        "views": [v.name for v in template.views],
    }


def _list_projects_via_rest(owner: str) -> list[dict[str, Any]]:
    """List projects using GitHub REST API."""
    for endpoint in (f"users/{owner}/projectsV2", f"orgs/{owner}/projectsV2"):
        cmd = [CONST_GH_CLI, "api", endpoint, "-H", "Accept: application/vnd.github+json"]
        proc = run_gh(cmd, check=False, quiet=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        data = extract_json_payload(proc.stdout)
        if isinstance(data, list) and data:
            return [
                {
                    "number": p.get("number", 0),
                    "title": p.get("title", ""),
                    "state": p.get("state", "open"),
                    "id": p.get("node_id") or str(p.get("id", "")),
                    "url": p.get("html_url")
                    or f"https://github.com/users/{owner}/projects/{p.get('number', '')}",
                }
                for p in data
                if isinstance(p, dict)
            ]
    return []


def _format_project_list_entry(p: dict[str, Any]) -> dict[str, Any]:
    """Format single project dictionary for list_remote_projects output."""
    return {
        "number": p.get("number", 0),
        "title": p.get("title", ""),
        "state": "closed" if p.get("closed", False) else "open",
        "id": p.get("id", ""),
        "url": p.get("url", ""),
    }


def _list_projects_via_cli(owner: str) -> list[dict[str, Any]]:
    """List projects using gh project list CLI command."""
    owner_arg = _resolve_project_owner_arg(owner)
    cmd = [CONST_GH_CLI, "project", "list", "--owner", owner_arg, "--format", "json"]
    proc = _run_project_cli(cmd, owner_arg=owner_arg)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    data = extract_json_payload(proc.stdout)
    raw = (
        data.get("projects", [])
        if isinstance(data, dict)
        else (data if isinstance(data, list) else [])
    )
    return [_format_project_list_entry(p) for p in raw if isinstance(p, dict)]


def list_remote_projects(owner: str) -> list[dict[str, Any]]:
    """List GitHub Projects v2 boards belonging to the user or organization."""
    return _list_projects_via_rest(owner) or _list_projects_via_cli(owner)


def audit_remote_project_views(owner: str, repo: str, template: ProjectTemplate) -> dict[str, Any]:
    """Audit remote project views against template requirements."""
    _, proj_num, existing_views = get_remote_project_views(owner, repo)
    if not proj_num:
        return {
            "project_number": None,
            "compliant": False,
            "missing_views": [v.name for v in template.views],
            "matching_views": [],
            "total_remote_views": 0,
        }

    existing_names = {v.get("name", "").strip().lower() for v in existing_views}
    expected_names = [v.name for v in template.views]
    missing = [name for name in expected_names if name.lower() not in existing_names]
    matching = [name for name in expected_names if name.lower() in existing_names]

    return {
        "project_number": proj_num,
        "compliant": len(missing) == 0,
        "missing_views": missing,
        "matching_views": matching,
        "total_remote_views": len(existing_views),
    }


def audit_project_drift(owner: str, repo: str, template: ProjectTemplate) -> dict[str, Any]:
    """Audit project board health, field presence, and view alignment."""
    views_audit = audit_remote_project_views(owner, repo, template)
    matched = find_remote_project(owner, template.name, repo=repo)
    if not matched and template.short_name:
        matched = find_remote_project(owner, template.short_name, repo=repo)

    proj_num = matched.get("number") if matched else views_audit.get("project_number")
    return {
        "project_number": proj_num,
        "project_found": proj_num is not None,
        "views_compliant": views_audit.get("compliant", False),
        "missing_views": views_audit.get("missing_views", []),
        "matching_views": views_audit.get("matching_views", []),
    }
