"""GitHub Projects v2 declarative template schemas, view definitions, and task tracking sync."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError

logger = logging.getLogger(__name__)


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
    clean = heading.lower().replace("-", " ")
    if "completed" in clean or "done" in clean:
        return "Done"
    if "in progress" in clean or "wip" in clean:
        return "In Progress"
    if "pending" in clean or "backlog" in clean:
        return "Backlog"
    if "review" in clean:
        return "In Review"
    if "ready" in clean:
        return "Ready"
    return None


def _is_task_markdown(path: Path) -> bool:
    """Check whether path is an active task markdown file (excluding READMEs and archives)."""
    return (
        path.is_file()
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
    return [readme] if readme.is_file() else []


def _resolve_default_task_fallbacks(task_path: Path) -> list[Path] | None:
    """Resolve standard fallback locations when default task path is requested."""
    if task_path not in (Path("docs/agent/tasks"), Path("docs/agent/task.md")):
        return None
    tasks_dir = Path("docs/agent/tasks")
    if tasks_dir.is_dir():
        files = _find_active_task_files_in_dir(tasks_dir)
        if files:
            return files
    task_file = Path("docs/agent/task.md")
    return [task_file] if task_file.is_file() else None


def _resolve_task_files(task_path: Path) -> list[Path]:
    """Resolve task_path (file or directory) to a list of existing markdown task files."""
    if task_path.is_dir():
        return _find_active_task_files_in_dir(task_path)

    if task_path.is_file():
        if task_path == Path("docs/agent/task.md"):
            tasks_dir = Path("docs/agent/tasks")
            active = _find_active_task_files_in_dir(tasks_dir) if tasks_dir.is_dir() else []
            if active:
                return active
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
    """Check if subprocess output indicates a GitHub API rate limit exhaustion."""
    clean = output.lower()
    rate_limit_indicators = (
        "unknown owner type",
        "api rate limit already exceeded",
        "graphql_rate_limit",
        "rate limit exceeded",
    )
    if any(ind in clean for ind in rate_limit_indicators):
        raise GitHubOperationError(
            "GitHub GraphQL API rate limit is currently exhausted. "
            "Please wait for quota reset or utilize REST endpoints.",
            operation=operation,
            details={"output": output.strip()},
        )


def verify_project_auth_scopes() -> None:
    """Verify that the gh CLI has the necessary project/read:project OAuth scopes."""
    proc = run_subprocess(
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
        proc = run_subprocess(cmd, check=False, quiet=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, list):
                match = _find_project_in_list(data, name_or_short)
                if match:
                    return match
        except json.JSONDecodeError:
            continue
    return None


def _find_project_via_cli(owner: str, name_or_short: str) -> dict[str, Any] | None:
    """Fallback to searching projects via gh project list CLI."""
    proc = run_subprocess(
        [CONST_GH_CLI, "project", "list", "--owner", owner, "--format", "json"],
        check=False,
    )
    if proc.returncode != 0:
        err = f"{proc.stderr or ''} {proc.stdout or ''}"
        check_github_rate_limit_error(err, operation="find_remote_project")
        return None
    try:
        data = json.loads(proc.stdout or "{}")
        projects = (
            data.get("projects", [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        return _find_project_in_list(projects, name_or_short)
    except Exception:
        return None


def find_remote_project(owner: str, name_or_short: str) -> dict[str, Any] | None:
    """Locate an existing remote project by title or short name."""
    return _find_project_via_rest(owner, name_or_short) or _find_project_via_cli(
        owner, name_or_short
    )


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


def _fetch_project_item_urls(owner: str, project_number: int) -> set[str]:
    """Retrieve URLs of items currently present on the project board."""
    res = run_subprocess(
        [
            CONST_GH_CLI,
            "api",
            f"users/{owner}/projectsV2/{project_number}/items",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0 or not res.stdout:
        return set()
    try:
        items = json.loads(res.stdout)
        return {
            url
            for it in items
            if isinstance(it, dict)
            if (
                url := (it.get("content") or {}).get("html_url")
                or (it.get("content") or {}).get("url")
            )
        }
    except Exception:
        return set()


def _fetch_repository_issues(repo: str) -> list[dict[str, Any]]:
    """Retrieve candidate issues from the repository via GitHub API."""
    res = run_subprocess(
        [
            CONST_GH_CLI,
            "api",
            f"repos/{repo}/issues?state=all&per_page=30",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0 or not res.stdout:
        return []
    try:
        data = json.loads(res.stdout)
        return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def sync_repository_issues_to_project(
    owner: str,
    repo: str,
    project_number: int,
    dry_run: bool = False,
) -> int:
    """Synchronize open and active repository issues to the project board."""
    if dry_run:
        return 0

    existing_urls = _fetch_project_item_urls(owner, project_number)
    issues = _fetch_repository_issues(repo)
    added = 0

    for iss in issues:
        url = iss.get("html_url") or iss.get("url")
        if not url or url in existing_urls:
            continue
        add_proc = run_subprocess(
            [
                CONST_GH_CLI,
                "project",
                "item-add",
                str(project_number),
                "--owner",
                owner,
                "--url",
                url,
            ],
            check=False,
            quiet=True,
        )
        if add_proc.returncode == 0:
            added += 1
            existing_urls.add(url)

    return added


def infer_item_priority(labels: list[Any]) -> str:
    """Infer GitHub Projects Priority field from issue/PR taxonomy labels."""
    names = [lbl.get("name", "") if isinstance(lbl, dict) else str(lbl) for lbl in labels]
    for n in names:
        n_lower = n.lower()
        if "p0-critical" in n_lower:
            return "P0-Critical"
        if "p1-high" in n_lower:
            return "P1-High"
        if "p2-medium" in n_lower:
            return "P2-Medium"
        if "p3-low" in n_lower:
            return "P3-Low"
    return "P2-Medium"


def infer_item_status(
    state: str,
    labels: list[Any],
    is_pr: bool = False,
    has_open_pr: bool = False,
) -> str:
    """Infer GitHub Projects Status field from state, PR presence, and taxonomy labels."""
    st_upper = state.upper()
    if st_upper in ("CLOSED", "MERGED"):
        return "Done"

    # Open PRs and issues with active open PRs are In Review
    if is_pr or has_open_pr:
        return "In Review"

    names = [lbl.get("name", "") if isinstance(lbl, dict) else str(lbl) for lbl in labels]
    for n in names:
        n_lower = n.lower()
        if "status/blocked" in n_lower:
            return "Blocked"
        if "status/in-review" in n_lower:
            return "In Review"
        if "status/in-progress" in n_lower:
            return "In Progress"
        if "status/ready" in n_lower:
            return "Ready"
        if "status/backlog" in n_lower:
            return "Backlog"

    return "Ready"


TAXONOMY_CATEGORY_MAPPING: dict[str, tuple[str, str, str]] = {
    "type/feature": ("Major Project", "High", "High"),
    "type/security": ("Quick Win", "High", "Low"),
    "type/bug": ("Quick Win", "High", "Low"),
    "type/refactor": ("Foundation", "High", "Medium"),
    "type/infra": ("Foundation", "High", "Medium"),
    "type/test": ("Foundation", "Medium", "Medium"),
    "type/docs": ("Fill-In", "Medium", "Low"),
    "type/chore": ("Fill-In", "Low", "Low"),
}

PRIORITY_CATEGORY_MAPPING: dict[str, tuple[str, str, str]] = {
    "P0-Critical": ("Quick Win", "High", "Low"),
    "P1-High": ("Foundation", "High", "Medium"),
    "P2-Medium": ("Fill-In", "Medium", "Medium"),
    "P3-Low": ("Fill-In", "Low", "Low"),
}


def _match_taxonomy_labels(labels: list[Any], priority: str) -> tuple[str, str, str] | None:
    """Classify Project Category, Value, Effort from issue/PR taxonomy labels."""
    label_names = [lbl.get("name", "") if isinstance(lbl, dict) else str(lbl) for lbl in labels]
    for name in label_names:
        n_lower = name.lower()
        for type_key, mapping in TAXONOMY_CATEGORY_MAPPING.items():
            if type_key in n_lower:
                if priority in ("P0-Critical", "P1-High") and "bug" in n_lower:
                    return "Quick Win", "High", "Low"
                return mapping
    return None


def infer_item_category_value_effort(
    title: str, priority: str, labels: list[Any] | None = None
) -> tuple[str, str, str]:
    """Infer Category, Value, and Effort for GitHub Projects v2 custom fields."""
    if labels:
        matched = _match_taxonomy_labels(labels, priority)
        if matched is not None:
            return matched

    if priority == "P0-Critical":
        return "Quick Win", "High", "Low"

    t = title.lower()
    title_rules: list[tuple[tuple[str, ...], tuple[str, str, str]]] = [
        (
            ("tree-sitter", "ast graph", "observability", "loki", "daemon"),
            ("Major Project", "High", "High"),
        ),
        (("fastmcp", "mcp", "prompt grounding", "contract"), ("Quick Win", "High", "Low")),
        (
            ("vector", "store", "tier", "valkey", "ingest", "cache"),
            ("Foundation", "High", "Medium"),
        ),
        (("drift", "auditor", "usage", "docs", "chore"), ("Fill-In", "Medium", "Medium")),
    ]
    for keywords, mapping in title_rules:
        if any(k in t for k in keywords):
            return mapping

    return PRIORITY_CATEGORY_MAPPING.get(priority, ("Fill-In", "Medium", "Medium"))


def _fetch_repository_prs(repo: str) -> list[dict[str, Any]]:
    """Retrieve candidate PRs from the repository via GitHub API."""
    res = run_subprocess(
        [
            CONST_GH_CLI,
            "api",
            f"repos/{repo}/pulls?state=all&per_page=30",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0 or not res.stdout:
        return []
    try:
        data = json.loads(res.stdout)
        return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def _edit_project_item_field(
    owner: str, project_number: int, url: str, field_name: str, field_val: str
) -> bool:
    """Update a single custom field value on a project item."""
    edit_cmd = [
        CONST_GH_CLI,
        "project",
        "item-edit",
        str(project_number),
        "--owner",
        owner,
        "--url",
        url,
        "--field",
        field_name,
        "--value",
        field_val,
    ]
    proc = run_subprocess(edit_cmd, check=False, quiet=True)
    return proc.returncode == 0


def _reconcile_single_item(
    owner: str,
    project_number: int,
    item: dict[str, Any],
    dry_run: bool,
    has_open_pr: bool = False,
) -> bool:
    """Infer and apply all custom fields to a single candidate project item."""
    url = item.get("html_url") or item.get("url") or ""
    if not url:
        return False
    title = item.get("title", "")
    state = str(item.get("state", "OPEN"))
    labels = item.get("labels", [])

    is_pr = "/pull/" in url or "pull_request" in item
    priority = infer_item_priority(labels)
    status = infer_item_status(state, labels, is_pr=is_pr, has_open_pr=has_open_pr)
    category, val, eff = infer_item_category_value_effort(title, priority, labels=labels)

    if dry_run:
        return True

    fields = [
        ("Status", status),
        ("Priority", priority),
        ("Category", category),
        ("Value", val),
        ("Effort", eff),
    ]
    for fname, fval in fields:
        _edit_project_item_field(owner, project_number, url, fname, fval)
    return True


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


def reconcile_project_custom_fields(
    owner: str,
    repo: str,
    project_number: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Reconcile custom field values (Status, Priority, Category, Value, Effort) on project items."""
    existing_urls = _fetch_project_item_urls(owner, project_number)
    issues = _fetch_repository_issues(repo)
    prs = _fetch_repository_prs(repo)
    candidates = issues + prs

    open_pr_issue_numbers = _extract_linked_issue_numbers(prs)

    if not dry_run:
        for it in candidates:
            url = it.get("html_url") or it.get("url")
            if url and url not in existing_urls:
                add_proc = run_subprocess(
                    [
                        CONST_GH_CLI,
                        "project",
                        "item-add",
                        str(project_number),
                        "--owner",
                        owner,
                        "--url",
                        url,
                    ],
                    check=False,
                    quiet=True,
                )
                if add_proc.returncode == 0:
                    existing_urls.add(url)

    reconciled_count = 0
    for it in candidates:
        it_num = int(it.get("number", 0))
        has_pr = it_num in open_pr_issue_numbers
        if _reconcile_single_item(owner, project_number, it, dry_run, has_open_pr=has_pr):
            reconciled_count += 1

    return {
        "project_number": project_number,
        "owner": owner,
        "repo": repo,
        "items_evaluated": len(candidates),
        "items_reconciled": reconciled_count,
        "dry_run": dry_run,
    }


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

    matched = find_remote_project(owner, template.name)
    if not matched and template.short_name:
        matched = find_remote_project(owner, template.short_name)

    if not matched:
        matched = create_remote_project(owner, template.name)

    proj_num = int(matched.get("number", 1))
    linked = link_project_to_repository(proj_num, owner, repo)
    provisioned = provision_remote_project_fields(proj_num, owner, template.fields)
    items_added = sync_repository_issues_to_project(owner, repo, proj_num, dry_run=False)
    if reconcile_fields:
        reconcile_project_custom_fields(owner, repo, proj_num, dry_run=False)

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
    proc = run_subprocess(cmd, check=False, quiet=True)
    if proc.returncode != 0 or not proc.stdout:
        return None, None, []
    try:
        data = json.loads(proc.stdout)
        nodes = data.get("data", {}).get("repository", {}).get("projectsV2", {}).get("nodes", [])
        if not nodes:
            return None, None, []
        proj = nodes[0]
        views: list[dict[str, str]] = proj.get("views", {}).get("nodes", [])
        return proj.get("id"), proj.get("number"), views
    except json.JSONDecodeError, AttributeError, KeyError:
        return None, None, []


def _create_project_view(project_id: str, name: str, layout: str) -> bool:
    """Create a project view via GraphQL mutation."""
    layout_enum = _map_view_layout(layout)
    mutation = (
        f"mutation {{ createProjectV2View(input: {{ projectId: {json.dumps(project_id)}, "
        f"name: {json.dumps(name)}, layout: {layout_enum} }}) {{ projectV2View {{ id name }} }} }}"
    )
    proc = run_subprocess(
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
    proc = run_subprocess(
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
        proc = run_subprocess(cmd, check=False, quiet=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        try:
            data = json.loads(proc.stdout)
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
        except json.JSONDecodeError:
            continue
    return []


def _list_projects_via_cli(owner: str) -> list[dict[str, Any]]:
    """List projects using gh project list CLI command."""
    cmd = [CONST_GH_CLI, "project", "list", "--owner", owner, "--format", "json"]
    proc = run_subprocess(cmd, check=False, quiet=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
        raw = (
            data.get("projects", [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        return [
            {
                "number": p.get("number", 0),
                "title": p.get("title", ""),
                "state": "closed" if p.get("closed", False) else "open",
                "id": p.get("id", ""),
                "url": p.get("url", ""),
            }
            for p in raw
            if isinstance(p, dict)
        ]
    except Exception as exc:
        logger.debug("Failed to parse project list: %s", exc)
        return []


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
    matched = find_remote_project(owner, template.name)
    if not matched and template.short_name:
        matched = find_remote_project(owner, template.short_name)

    proj_num = matched.get("number") if matched else views_audit.get("project_number")
    return {
        "project_number": proj_num,
        "project_found": proj_num is not None,
        "views_compliant": views_audit.get("compliant", False),
        "missing_views": views_audit.get("missing_views", []),
        "matching_views": views_audit.get("matching_views", []),
    }
