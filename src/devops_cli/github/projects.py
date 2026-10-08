"""GitHub Projects v2: the board template, its views, and reconciling Status and Priority on its cards.

Neither `devops gh project sync` nor `devops gh project reconcile` adds a card: intake
(`devops roadmap intake`) is the one way an issue reaches the board, and a pull request gets no
card, its progress showing on its issue's (#892).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_GH_CLI, CONST_PROJECT_TEMPLATE_PATH
from devops_cli.config.defaults import (
    DEFAULT_GH_CACHE_TTL_SECONDS,
    DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
    DEFAULT_GH_MAX_PAGINATED_PAGES,
    DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC,
    DEFAULT_GH_PROJECT_ITEM_PAGE_POINTS,
    DEFAULT_GH_PROJECT_OPTION_COLOR,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.github.client import parse_paginated_json
from devops_cli.github.rate_limiter import (
    extract_json_payload,
    get_github_rate_limiter,
    run_gh,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.board_read import (
    BoardBudgetPayload,
    BoardItemsPage,
    GraphQLBudget,
    board_budget_args,
    board_items_args,
    read_cost,
    require_budget,
    require_floor,
    utc_clock,
)
from devops_cli.roadmap.store import ItemField, require_option

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


class MutationBudget:
    """Bounds the card field writes one reconcile run makes (`DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC`)."""

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


def project_template_path(template_path: Path | None = None) -> Path:
    """The template file given, or `.github/project-template.json` at the root of the checkout
    the command runs in, from any of its subdirectories (#1010)."""
    return template_path or find_repo_root() / CONST_PROJECT_TEMPLATE_PATH


def load_project_template(template_path: Path | None = None) -> ProjectTemplate:
    """Load and validate declarative GitHub Projects v2 template from JSON."""
    path = project_template_path(template_path)
    if not path.is_file():
        raise GitHubOperationError(
            f"Project template file not found: {path}",
            operation="load_project_template",
            details={"path": str(path)},
        )

    try:
        content = path.read_text(encoding="utf-8")
        return ProjectTemplate.model_validate_json(content)
    except Exception as exc:
        raise GitHubOperationError(
            f"Failed to load project template {path}: {exc}",
            operation="load_project_template",
            details={"path": str(path), "error": str(exc)},
        ) from exc


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


# The argument builders below are what the reads run and what `reconcile_dry_run` lists, so the
# request plan cannot drift from the run.
_USER_LOGIN_ARGS: tuple[str, ...] = ("api", "user", "--jq", ".login")
_OWNER_BOARD_ENDPOINTS: tuple[str, ...] = ("users/{owner}/projectsV2", "orgs/{owner}/projectsV2")
_REPOSITORY_BOARDS_QUERY = (
    "query($owner: String!, $repo: String!) { "
    "repository(owner: $owner, name: $repo) { "
    "projectsV2(first: 20) { nodes { number title id url } } } }"
)


def _owner_boards_args(endpoint: str, owner: str) -> list[str]:
    """The REST read of `owner`'s boards from one of `_OWNER_BOARD_ENDPOINTS`."""
    return ["api", endpoint.format(owner=owner), "-H", "Accept: application/vnd.github+json"]


def _project_list_args(owner_arg: str) -> list[str]:
    """`gh project list` of `owner_arg`'s boards."""
    return ["project", "list", "--owner", owner_arg, "--format", "json"]


def _repository_boards_args(owner: str, repo: str) -> list[str]:
    """The GraphQL read of the boards linked to `repo`."""
    clean_repo = repo.split("/")[-1] if "/" in repo else repo
    clean_owner = owner.split("/")[0] if "/" in owner else owner
    return [
        "api",
        "graphql",
        "-f",
        f"query={_REPOSITORY_BOARDS_QUERY}",
        "-F",
        f"owner={clean_owner}",
        "-F",
        f"repo={clean_repo}",
    ]


def _find_project_via_rest(owner: str, name_or_short: str) -> dict[str, Any] | None:
    """Attempt to locate a remote project via GitHub REST API."""
    for endpoint in _OWNER_BOARD_ENDPOINTS:
        proc = run_gh([CONST_GH_CLI, *_owner_boards_args(endpoint, owner)], check=False, quiet=True)
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
    proc = run_gh([CONST_GH_CLI, *_USER_LOGIN_ARGS], check=False, quiet=True)
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
    proc = _run_project_cli([CONST_GH_CLI, *_project_list_args(owner_arg)], owner_arg=owner_arg)
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
    proc = run_gh([CONST_GH_CLI, *_repository_boards_args(owner, repo)], check=False, quiet=True)
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


def find_project_by_template(owner: str, repo: str, template: ProjectTemplate) -> int | None:
    """The number of `owner`'s board named as `template` names it, by title, then short name."""
    for name in _template_names(template):
        matched = find_remote_project(owner, name, repo=repo)
        if matched and matched.get("number"):
            return int(matched["number"])
    return None


def _template_names(template: ProjectTemplate) -> list[str]:
    """The names a board made from `template` goes by: its title, then its short name."""
    return [template.name, *([template.short_name] if template.short_name else [])]


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


def _project_login(owner: str) -> str:
    """The login a board read names its owner by; `@me` is the signed-in user's."""
    login = owner.strip()
    return (_get_authenticated_user() or login) if login == "@me" else login


def _read_failure(proc: subprocess.CompletedProcess[str], what: str, operation: str) -> Exception:
    """The error a read of `what` that exited non-zero raises: the rate limit's when its output
    names one."""
    err_output = f"{proc.stderr or ''} {proc.stdout or ''}".strip()
    check_github_rate_limit_error(err_output, operation=operation)
    return GitHubOperationError(
        f"Failed to read {what} (exit {proc.returncode}): {err_output[:256]}",
        operation=operation,
        details={"read": what[:256]},
    )


def _gh_read[Payload: BaseModel](
    args: list[str], model: type[Payload], what: str, operation: str = "fetch_project_items"
) -> Payload:
    """One read through `run_gh`, which charges a GraphQL reply the points its `rateLimit`
    reports; raises when GitHub can't be read or answers malformed."""
    proc = run_gh([CONST_GH_CLI, *args], check=False, quiet=True, use_cache=False)
    if proc.returncode != 0:
        raise _read_failure(proc, what, operation)
    try:
        return model.model_validate_json(proc.stdout or "")
    except ValueError as exc:
        raise GitHubOperationError(
            f"GitHub returned malformed {what}: {str(exc)[:256]}",
            operation=operation,
            details={"read": what[:256]},
        ) from exc


def _read_board(login: str, project_number: int) -> dict[str, dict[str, str | None]]:
    """Every card on the board not archived, by its issue or pull request URL, with its fields.

    The read starts with the roadmap store's budget query (#1125), whose reply reports GraphQL's
    own count of the points left: a read that would leave fewer than the floor refuses there,
    having spent nothing on pages. When the ledger holds no GraphQL entry, or one past its
    reset, `run_gh` refreshes it before sending the query, so an unknown quota is read rather
    than taken as spent. The board is then read a page at a time, each page charging the points
    it cost, and the read stops before a page while fewer than the floor are left. Raises when
    the board cannot be read whole, so a failed read never looks like an empty board.
    """
    what = f"project #{project_number} items"
    probe = _gh_read(
        board_budget_args(login, project_number, ""),
        BoardBudgetPayload,
        MESSAGES.project.budget_read.format(what=what),
    )
    require_budget(
        probe.rate_limit,
        read_cost(probe.items.total_count, DEFAULT_GH_PROJECT_ITEM_PAGE_POINTS),
        what,
    )
    listing: dict[str, dict[str, Any]] = {}
    total = probe.items.total_count
    after: str | None = None
    budget: GraphQLBudget = probe.rate_limit
    for page in range(1, DEFAULT_GH_MAX_PAGINATED_PAGES + 1):
        if page > 1:
            require_floor(budget, what, page)
        read = _gh_read(
            board_items_args(login, project_number, "", after=after), BoardItemsPage, what
        )
        budget = read.rate_limit
        total = read.items.total_count
        listing.update((entry["id"], entry) for entry in read.listed())
        after = read.next_cursor()
        if after is None:
            break
    _require_whole(
        project_number,
        len(listing),
        total,
        what,
        "fetch_project_items",
        incomplete=after is not None,
    )
    return {
        url: _extract_item_fields(entry)
        for entry in listing.values()
        if (url := _extract_item_url(entry))
    }


def _require_whole(
    project_number: int,
    received: int,
    total: int,
    what: str,
    operation: str,
    *,
    incomplete: bool = False,
) -> None:
    """Raise when a read of `what` got fewer than its `total`, or stopped with a page left, so
    a partial read never looks whole."""
    if incomplete or received < total:
        raise GitHubOperationError(
            f"Read {received} of {total} {what}, so the read is incomplete.",
            operation=operation,
            details={"project_number": project_number, "received": received, "total": total},
        )


def _read_field_options(login: str, project_number: int) -> dict[str, tuple[str, ...]]:
    """The board's own fields' options by field name, which are the values a write can set.

    Raises when the fields can't be read whole or the board has no Status options, so an unread
    field never lets every unset card default to New over its `status/*` label.
    """
    from devops_cli.roadmap.github_store import FieldListingPayload, field_list_args

    what = f"project #{project_number} fields"
    listing = _gh_read(
        field_list_args(login, project_number), FieldListingPayload, what, "fetch_project_fields"
    )
    _require_whole(
        project_number, len(listing.fields), listing.total_count, what, "fetch_project_fields"
    )
    options = listing.options()
    if not options.get(ItemField.STATUS):
        raise GitHubOperationError(
            MESSAGES.project.no_status_options.format(number=project_number),
            operation="fetch_project_fields",
            details={"project_number": project_number},
        )
    return options


def _repository_list_args(repo: str, kind: str, state: str) -> list[str]:
    """Every page of `repo`'s issues or pull requests in `state`, as one `gh api --paginate`."""
    return [
        "api",
        "--paginate",
        f"repos/{repo}/{kind}?state={state}&per_page=100",
        "-H",
        "Accept: application/vnd.github+json",
    ]


def _fetch_repository_list(repo: str, kind: str, state: str) -> list[dict[str, Any]]:
    """Fetch every page of a repository's issues or pull requests, raising if GitHub can't be read."""
    res = run_gh(
        [CONST_GH_CLI, *_repository_list_args(repo, kind, state)],
        check=False,
        quiet=True,
        use_cache=True,
        cache_ttl=DEFAULT_GH_CACHE_TTL_SECONDS,
    )
    if res.returncode != 0:
        raise _read_failure(res, f"{kind} for {repo}", f"fetch_{kind}")
    return parse_paginated_json(res.stdout or "")


def _fetch_repository_issues(repo: str, state: str = "open") -> list[dict[str, Any]]:
    """Retrieve candidate issues from the repository via GitHub API.

    The issues endpoint also returns pull requests, without their merge state; those come
    from the pulls endpoint instead, so each pull request is reconciled once.
    """
    return [it for it in _fetch_repository_list(repo, "issues", state) if "pull_request" not in it]


class FieldChange(BaseModel):
    """One board field change that reconcile plans or makes, and what decided it."""

    url: str
    field: str
    old: str | None
    new: str
    source: str

    @property
    def item(self) -> str:
        """The item as a change table names it: `#` and its number."""
        return "#" + self.url.rstrip("/").rsplit("/", 1)[-1]


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


ReconcileMode = Literal["dry-run", "plan", "write"]
"""`dry-run` makes no request and lists the requests a run makes; `plan` reads the board and the
repository and lists the changes; `write` makes them."""


class ReconcileResult(BaseModel):
    """What a reconcile run planned and made, what it left, and why it stopped early.

    Changes are applied in the order planned and the run stops at the first it can't make, so
    the planned changes are always the applied ones followed by the remaining ones.
    """

    model_config = ConfigDict(frozen=True)

    project_number: int | None
    mode: ReconcileMode
    items_evaluated: int = 0
    planned: list[FieldChange] = Field(default_factory=list)
    applied: list[FieldChange] = Field(default_factory=list)
    stop: str | None = None
    awaiting_intake: int | None = None
    requests: tuple[PlannedRequest, ...] = ()

    @property
    def remaining(self) -> list[FieldChange]:
        """The planned changes a write run did not make."""
        return self.planned[len(self.applied) :] if self.mode == "write" else []

    @property
    def shown(self) -> list[FieldChange]:
        """The changes the run reports: those it plans, or those it made."""
        return self.applied if self.mode == "write" else self.planned

    def summary(self) -> str:
        """The run's last line when it planned or made every change."""
        texts = MESSAGES.project
        template = texts.summary_write if self.mode == "write" else texts.summary_plan
        return template.format(
            items=len({change.url for change in self.shown}),
            evaluated=self.items_evaluated,
            number=self.project_number,
            changes=len(self.shown),
        )

    def stop_line(self) -> str | None:
        """Why a write run stopped before making every planned change, and what it left."""
        if self.stop is None:
            return None
        texts = MESSAGES.project
        count = len(self.remaining)
        remaining = texts.remaining[count != 1].format(count=count)
        return texts.stopped.format(reason=self.stop, remaining=remaining)

    def intake_line(self) -> str | None:
        """How many open issues wait for intake, when the run listed open issues and found any."""
        count = self.awaiting_intake
        if not count:
            return None
        return MESSAGES.project.awaiting_intake[count != 1].format(count=count)


def _item_url(item: Mapping[str, Any]) -> str:
    return str(item.get("html_url") or item.get("url") or "")


def _awaiting_intake(
    issues: list[dict[str, Any]], board: Collection[str], state: str
) -> int | None:
    """The open issues not on the board; None when the run listed no open issue."""
    if state == "closed":
        return None
    return sum(
        1
        for issue in issues
        if str(issue.get("state", "")).lower() == "open" and _item_url(issue) not in board
    )


def _stop_before_write(budget: MutationBudget) -> str | None:
    """Why the next write must not run: the mutation budget is spent, or the ledger, which
    the board's pages and the other runs sharing the identity keep, holds fewer GraphQL points
    than the floor. An entry that is unknown or past its reset is left to `run_gh`, whose
    `acquire` refreshes it before the write."""
    texts = MESSAGES.project
    if budget.is_exhausted:
        return texts.stop_budget.format(limit=budget.limit)
    quota = get_github_rate_limiter().get_quota("graphql")
    if quota.is_valid() and (quota.remaining or 0) < DEFAULT_GH_GRAPHQL_BUDGET_FLOOR:
        return texts.stop_quota.format(
            remaining=quota.remaining,
            reset=utc_clock(datetime.fromtimestamp(quota.reset_epoch or 0, UTC)),
            floor=DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
        )
    return None


def _item_edit_args(login: str, project_number: int | str, change: FieldChange) -> list[str]:
    from devops_cli.roadmap.github_store import item_edit_args

    return item_edit_args(login, project_number, change.url, change.field, ["--value", change.new])


def _write_change(login: str, project_number: int, change: FieldChange) -> str | None:
    """Make one planned change; None when it was made, else why it failed."""
    proc = run_gh(
        [CONST_GH_CLI, *_item_edit_args(login, project_number, change)], check=False, quiet=True
    )
    if proc.returncode == 0:
        return None
    error = f"{proc.stderr or ''} {proc.stdout or ''}".strip() or f"exit {proc.returncode}"
    return MESSAGES.project.stop_write_failed.format(
        field=change.field, item=change.item, error=error[:256]
    )


def _apply_changes(
    login: str, project_number: int, planned: list[FieldChange], budget: MutationBudget
) -> tuple[list[FieldChange], str | None]:
    """Make the planned changes in order, stopping at the first that can't be made: the
    changes made, and why the run stopped, or None when it made them all."""
    applied: list[FieldChange] = []
    for change in planned:
        stop = _stop_before_write(budget) or _write_change(login, project_number, change)
        if stop is not None:
            return applied, stop
        budget.record_mutation()
        applied.append(change)
    return applied, None


def _plan_changes(
    candidates: list[dict[str, Any]],
    board: Mapping[str, Mapping[str, str | None]],
    linked: set[int],
    status_options: Collection[str],
) -> list[FieldChange]:
    """Every change the cards already on the board need, in the order the candidates came."""
    return [
        change
        for item in candidates
        for change in plan_item_changes(
            item,
            board[_item_url(item)],
            has_open_pr=int(item.get("number", 0)) in linked,
            status_options=status_options,
        )
    ]


def reconcile_project_custom_fields(
    owner: str,
    repo: str,
    project_number: int,
    *,
    mode: Literal["plan", "write"] = "write",
    state: str = "open",
    budget: MutationBudget | None = None,
) -> ReconcileResult:
    """Reconcile Status and Priority on the cards already on the board, listing every change.

    Reconcile adds no card: an issue off the board waits for intake, and a pull request gets no
    card. It reads the board (refusing to start when GraphQL's budget can't cover the read), the
    board's field options and the repository's issues and pull requests in `state`, then plans
    every change before making any, so `plan` and `write` evaluate the same cards and plan the
    same changes. A planned value the board's field has no option for refuses the run before
    any write, naming the value, so a write that would fail on every run never blocks the
    changes after it. `write` makes the changes in order until the mutation budget is spent,
    GraphQL's points fall below the floor or a write fails, and the result says which.
    """
    login = _project_login(owner)
    board = _read_board(login, project_number)
    options = _read_field_options(login, project_number)
    issues = _fetch_repository_issues(repo, state=state)
    prs = _fetch_repository_prs(repo, state=state)
    on_board = [item for item in issues + prs if _item_url(item) in board]
    linked = _extract_linked_issue_numbers(prs)
    planned = _plan_changes(on_board, board, linked, options[ItemField.STATUS])
    for change in planned:
        require_option(options, ItemField(change.field), change.new)
    result = ReconcileResult(
        project_number=project_number,
        mode=mode,
        items_evaluated=len(on_board),
        planned=planned,
        awaiting_intake=_awaiting_intake(issues, board, state),
    )
    if mode == "plan":
        return result
    applied, stop = _apply_changes(login, project_number, planned, budget or MutationBudget())
    return result.model_copy(update={"applied": applied, "stop": stop})


def reconcile_dry_run(
    owner: str,
    repo: str,
    project_number: int | None,
    *,
    state: str = "open",
    template: ProjectTemplate | None = None,
    writes: bool = True,
) -> ReconcileResult:
    """The requests a reconcile run makes, in order, none of them made (#412).

    Without a board number the run first finds the board `template` names. `writes` False
    lists a `plan` run, which stops before the writes.
    """
    from devops_cli.roadmap.github_store import field_list_args
    from devops_cli.roadmap.request_plan import planned_gh

    texts = MESSAGES.project
    targets, placeholders = texts.request_targets, texts.request_placeholders
    board = str(project_number) if project_number else placeholders["board"]
    login = placeholders["login"] if owner.strip() == "@me" else owner.strip()
    requests: list[PlannedRequest] = []
    if project_number is None and template is not None:
        requests.extend(_find_board_requests(owner, repo, _template_names(template)))
    if owner.strip() == "@me":
        requests.append(planned_gh(list(_USER_LOGIN_ARGS), targets["login"]))
    requests.extend(
        [
            planned_gh(board_budget_args(login, board, ""), targets["budget"].format(board=board)),
            planned_gh(board_items_args(login, board, ""), targets["first"].format(board=board)),
            planned_gh(
                board_items_args(login, board, "", after=placeholders["cursor"]),
                targets["page"].format(board=board),
                repeat=MESSAGES.roadmap.plan_repeat_board_page,
            ),
            planned_gh(field_list_args(login, board), targets["fields"].format(board=board)),
            planned_gh(
                _repository_list_args(repo, "issues", state),
                targets["issues"].format(state=state, repo=repo),
            ),
            planned_gh(
                _repository_list_args(repo, "pulls", state),
                targets["pulls"].format(state=state, repo=repo),
            ),
        ]
    )
    if writes:
        change = FieldChange(
            url=placeholders["url"],
            field=placeholders["field"],
            old=None,
            new=placeholders["value"],
            source="",
        )
        requests.append(
            planned_gh(
                _item_edit_args(login, board, change),
                targets["edit"].format(board=board),
                repeat=texts.request_repeat_edit.format(
                    limit=DEFAULT_GH_MAX_PROJECT_MUTATIONS_PER_SYNC,
                    floor=DEFAULT_GH_GRAPHQL_BUDGET_FLOOR,
                ),
            )
        )
    return ReconcileResult(
        project_number=project_number,
        mode="dry-run",
        requests=tuple(requests),
    )


def _find_board_requests(owner: str, repo: str, names: list[str]) -> list[PlannedRequest]:
    """What `find_project_by_template` reads: for each name, until a board answers to it, the
    repository's linked boards, then the owner's by REST, then by `gh project list`."""
    from devops_cli.roadmap.request_plan import planned_gh

    texts = MESSAGES.project
    targets, conditions = texts.request_targets, texts.request_conditions
    owner_arg = texts.request_placeholders["owner_arg"].format(owner=owner)
    requests: list[PlannedRequest] = []
    for index, name in enumerate(names):
        earlier = conditions["not_found"].format(names=" or ".join(f"'{n}'" for n in names[:index]))
        unmatched = conditions["not_found"].format(
            names=" or ".join(f"'{n}'" for n in names[: index + 1])
        )
        found = targets["find"].format(name=name)
        requests.append(
            planned_gh(
                _repository_boards_args(owner, repo),
                targets["repo_boards"].format(repo=repo, found=found),
                condition=earlier if index else "",
            )
        )
        requests.extend(
            planned_gh(
                _owner_boards_args(endpoint, owner),
                targets["owner_boards"].format(owner=owner, found=found),
                condition=unmatched,
            )
            for endpoint in _OWNER_BOARD_ENDPOINTS
        )
        requests.append(
            planned_gh(
                list(_USER_LOGIN_ARGS),
                targets["login"],
                condition=f"{unmatched}{conditions['login_unread']}",
            )
        )
        requests.append(
            planned_gh(
                _project_list_args(owner_arg),
                targets["project_list"].format(owner=owner, found=found),
                condition=unmatched,
                repeat=texts.request_repeat_owner_fallback,
            )
        )
    return requests


class ProjectSyncResult(BaseModel):
    """What `devops gh project sync` did: the board it found or made, the fields it created,
    and reconcile's outcome. A dry run reads nothing, so it reports no board."""

    project_number: int | None = None
    project_title: str
    owner: str
    repo: str
    fields_provisioned: list[str] = Field(default_factory=list)
    dry_run: bool = False
    linked: bool = False
    reconcile: ReconcileResult | None = None


def _find_or_create_board(owner: str, repo: str, template: ProjectTemplate) -> int:
    """The number of the board `template` names, created when there is none."""
    number = find_project_by_template(owner, repo, template)
    if number is not None:
        return number
    created = create_remote_project(owner, template.name).get("number")
    if not created:
        raise GitHubOperationError(
            f"GitHub created board '{template.name}' but returned no number for it.",
            operation="create_remote_project",
            details={"owner": owner[:256], "title": template.name[:256]},
        )
    return int(created)


def sync_remote_project(
    owner: str,
    repo: str,
    template: ProjectTemplate,
    dry_run: bool = False,
    reconcile_fields: bool = True,
) -> ProjectSyncResult:
    """Find or create the template's board, link it, create the template fields it lacks, and
    reconcile Status and Priority on the cards already on it. Sync adds no card. A dry run
    makes no request."""
    result = ProjectSyncResult(project_title=template.name, owner=owner, repo=repo, dry_run=dry_run)
    if dry_run:
        return result

    verify_project_auth_scopes()
    number = _find_or_create_board(owner, repo, template)
    linked = link_project_to_repository(number, owner, repo)
    provisioned = provision_remote_project_fields(number, owner, template.fields)
    reconciled = (
        reconcile_project_custom_fields(owner, repo, number, mode="write")
        if reconcile_fields
        else None
    )
    return result.model_copy(
        update={
            "project_number": number,
            "fields_provisioned": provisioned,
            "linked": linked,
            "reconcile": reconciled,
        }
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
