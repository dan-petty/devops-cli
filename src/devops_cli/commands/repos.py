"""Repos command group: clone-org, clone, list, update."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient

import typer

from devops_cli.commands.workspace import sync_from_repos
from devops_cli.config.constants import (
    CONST_BRANCH_TYPES,
    CONST_GITHUB_HOST,
    CONST_GITHUB_REPO_SUFFIX,
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_URL_SCHEME_HTTPS,
    CONST_VSCODE_WORKSPACE_FILE,
)
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.exceptions import DevOpsCLIError, GitOperationError
from devops_cli.git.branch_form import is_valid_slug
from devops_cli.git.git_plans import (
    plan_clone,
    plan_clone_org,
    plan_reload_workspace,
    plan_repo_sync,
    reload_workspace_argv,
)
from devops_cli.git.operations import (
    clone_repo,
    current_branch,
    fetch_all,
    iter_workspace_repos,
    parse_clone_destination,
    pull_tracking,
)
from devops_cli.git.worktree_add import (
    ReclaimResult,
    WorktreeAddReport,
    add_worktree,
    reclaim_merged_worktrees,
)
from devops_cli.git.worktree_inventory import inventory_worktrees, plan_prune, prune_worktrees
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_bytes,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    track_progress,
)
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.roadmap.claim import claim_as_agent, claim_request_lines
from devops_cli.security.sanitizer import mask_secrets

app = new_typer(help=HELP.repos.app, no_args_is_help=True)


# =============================================================================
# Repos & Workspace Synchronization Helpers
# =============================================================================


def _github_https_url(full_name: str) -> str:
    return f"{CONST_URL_SCHEME_HTTPS}{CONST_GITHUB_HOST}/{full_name}{CONST_GITHUB_REPO_SUFFIX}"


def _require_client() -> GitHubClient:
    """The session's client, exiting with the unauthenticated error when gh has no token."""
    from devops_cli.github.session import get_github_session

    session = get_github_session()
    return session.client


def _current_branch(repo_dir: Path) -> str:
    try:
        return current_branch(repo_dir) or "HEAD detached"
    except GitOperationError:
        return "unknown"


def _resolve_workspace_file(root: Path, workspace_file: Path) -> Path:
    if workspace_file.is_absolute():
        return workspace_file
    if workspace_file == CONST_VSCODE_WORKSPACE_FILE:
        return root.parent / workspace_file
    return workspace_file


def _reload_workspace(workspace_file: Path) -> None:
    from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS

    try:
        run_subprocess(
            reload_workspace_argv(workspace_file),
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        from devops_cli.lang import MESSAGES

        print_warning(MESSAGES.messages.vscode_cli_unavailable, prefix=False)


def _sync_and_reload_workspace(root: Path, ws_file: Path) -> None:
    sync_from_repos(root, ws_file)
    _reload_workspace(ws_file)


def _resolve_safe_org_dir(root: Path, org_name: str) -> Path:
    """Validate organization name against path traversal and return resolved directory."""
    try:
        validate_no_path_traversal(org_name, label="Organization name")
    except Exception as exc:
        print_error(f"Invalid organization name: {exc}", prefix=False)
        raise typer.Exit(1) from exc

    org_dir = (root / org_name).resolve()
    if not org_dir.is_relative_to(root):
        print_error("Invalid destination path: path traversal not allowed.", prefix=False)
        raise typer.Exit(1)
    return org_dir


def _clone_single_org_repo(repo: Any, org_dir: Path) -> None:
    """Clone a single repository within the validated organization directory."""
    try:
        validate_no_path_traversal(repo.name, label="Repository name")
    except Exception:
        print_error(f"skip {repo.name} (path traversal detected)")
        return
    dest = (org_dir / repo.name).resolve()
    if not dest.is_relative_to(org_dir):
        print_error(f"skip {repo.name} (path traversal detected)")
        return
    if dest.exists():
        print_warning(f"skip {repo.name} (already exists)")
        return
    try:
        clone_repo(_github_https_url(repo.full_name), dest)
        print_success(f"done {repo.name}")
    except (OSError, subprocess.SubprocessError, Exception) as exc:
        print_error(f"fail {repo.name}: {mask_secrets(str(exc))}")


# =============================================================================
# Command: devops repos clone-org
# =============================================================================


@app.command("clone-org")
@dry_run_class("request-plan")
def clone_org(
    org: Annotated[
        str | None,
        typer.Argument(help=HELP.repos.org_name, show_default=False),
    ] = None,
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    private: Annotated[bool, typer.Option("--private/--no-private")] = True,
    forks: Annotated[bool, typer.Option("--forks/--no-forks")] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Clone all repos from a GitHub org into `repos/<org>/.`."""
    settings = load_settings()
    org_name = org or settings.github.default_org
    if not org_name:
        print_error(MESSAGES.repos.no_org_configured, prefix=False)
        raise typer.Exit(1)

    root = (base_dir or settings.repos.base_dir).resolve()
    org_dir = _resolve_safe_org_dir(root, org_name)
    if dry_run or is_dry_run():
        render_request_plan(
            MESSAGES.repos.clone_org_dry_run_heading,
            plan_clone_org(org_name, org_dir, settings.workspace.file, include_private=private),
            [MESSAGES.repos.workspace_dry_run_note.format(path=settings.workspace.file)],
        )
        return
    client = _require_client()

    repos = client.get_org_repos(
        org_name,
        include_private=private,
        include_forks=forks,
        include_archived=False,
    )
    org_dir.mkdir(parents=True, exist_ok=True)

    print_info(
        MESSAGES.repos.cloning_org_repos.format(count=len(repos), dest=org_dir), prefix=False
    )
    for repo in track_progress(repos, description="Cloning..."):
        _clone_single_org_repo(repo, org_dir)

    _sync_and_reload_workspace(root, settings.workspace.file)


# =============================================================================
# Command: devops repos clone
# =============================================================================


@app.command()
@dry_run_class("request-plan")
def clone(
    url: Annotated[str, typer.Argument(help=HELP.repos.repo_url)],
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Clone an individual repository into `repos/<org>/<name>/.` (or `repos/_standalone/<name>/.`)."""
    if url.startswith("-"):
        print_error(MESSAGES.repos.invalid_url_hyphen, prefix=False)
        raise typer.Exit(1)

    settings = load_settings()
    root = (base_dir or settings.repos.base_dir).resolve()
    try:
        org_name, raw_name = parse_clone_destination(url)
        validate_no_path_traversal(org_name, label="Organization name")
        validate_no_path_traversal(raw_name, label="Repository name")
    except Exception as exc:
        print_error(MESSAGES.repos.invalid_dest_path, prefix=False)
        raise typer.Exit(1) from exc

    dest_dir = (root / org_name).resolve()
    dest = (dest_dir / raw_name).resolve()
    if (
        not dest.is_relative_to(root)
        or not dest.is_relative_to(dest_dir)
        or org_name in (".", "..")
        or raw_name in (".", "..")
    ):
        print_error(MESSAGES.repos.invalid_dest_path, prefix=False)
        raise typer.Exit(1)

    if dest.exists():
        print_warning(MESSAGES.repos.already_exists.format(dest=dest), prefix=False)
        raise typer.Exit(1)

    if dry_run or is_dry_run():
        render_request_plan(
            MESSAGES.repos.clone_dry_run_heading,
            plan_clone(mask_secrets(url), dest, settings.workspace.file),
            [MESSAGES.repos.workspace_dry_run_note.format(path=settings.workspace.file)],
        )
        return

    dest_dir.mkdir(parents=True, exist_ok=True)
    masked_url = mask_secrets(url)
    print_info(MESSAGES.repos.cloning_repo.format(url=masked_url, dest=dest), prefix=False)
    clone_repo(url, dest)
    _sync_and_reload_workspace(root, settings.workspace.file)
    print_success(MESSAGES.repos.done, prefix=False)


# =============================================================================
# Command: devops repos list
# =============================================================================


@app.command("list")
@dry_run_class("no-external-request")
def list_repos(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List all cloned repositories."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        print_warning(MESSAGES.repos.repos_dir_not_found.format(root=root), prefix=False)
        raise typer.Exit(0)

    rows = [
        [repo_dir.parent.name, repo_dir.name, _current_branch(repo_dir)]
        for repo_dir in iter_workspace_repos(root)
    ]

    print_table(
        title=MESSAGES.repos.table_title_cloned.format(root=root),
        columns=[("Org / Group", "cyan"), "Repository", ("Branch", "green")],
        rows=rows,
    )


# =============================================================================
# Command: devops repos sync / update
# =============================================================================


@app.command("sync")
@app.command()
@dry_run_class("request-plan")
def update(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    pull: Annotated[bool, typer.Option("--pull/--no-pull")] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Fetch (and optionally pull) all tracking branches across repos."""
    settings = load_settings()
    root = (base_dir or settings.repos.base_dir).resolve()

    repos_list = list(iter_workspace_repos(root))
    if not repos_list:
        print_warning(MESSAGES.repos.no_repos_found, prefix=False)
        raise typer.Exit(0)

    if dry_run or is_dry_run():
        _plan_update(repos_list, settings.workspace.file, pull=pull)
        return

    failed = False
    for repo_dir in track_progress(repos_list, description="Updating..."):
        label = repo_label(repo_dir)
        try:
            fetch_all(repo_dir)
            if pull:
                pull_tracking(repo_dir)
            print_success(f"{label}")
        except (DevOpsCLIError, OSError, subprocess.SubprocessError, Exception) as exc:
            failed = True
            print_error(f"{label}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)
    if failed:
        raise typer.Exit(1)


def _plan_update(repos_list: list[Path], ws_file: Path, *, pull: bool) -> None:
    """Print the fetches, pulls and the workspace reload of `repos sync`, and make none. A
    repository whose plan fails is reported as the run reports it, and the exit status is 1."""
    requests: list[PlannedRequest] = []
    failed = False
    for repo_dir in repos_list:
        label = repo_label(repo_dir)
        try:
            requests.extend(plan_repo_sync(repo_dir, label, pull=pull))
        except (DevOpsCLIError, OSError, ValueError) as exc:
            failed = True
            print_error(f"{label}: {exc}")
    requests.extend(plan_reload_workspace(ws_file))
    render_request_plan(
        MESSAGES.repos.sync_dry_run_heading,
        requests,
        [MESSAGES.repos.workspace_dry_run_note.format(path=ws_file)],
    )
    if failed:
        raise typer.Exit(1)


# =============================================================================
# Subcommand Group: devops repos worktrees
# =============================================================================

worktrees_app = new_typer(help=HELP.repos.worktrees_app, no_args_is_help=True)
app.add_typer(worktrees_app, name="worktrees")


def _format_worktree_table_row(entry: Any) -> list[str]:
    """Format single worktree entry for tabular display."""
    branch = entry.branch or "(detached)"
    dirty = "?" if entry.dirty is None else str(entry.dirty)
    locked = (
        f"locked=true ({entry.lock_reason})"
        if (entry.locked and entry.lock_reason)
        else ("locked=true" if entry.locked else "locked=false")
    )
    prunable = (
        f"prunable=true ({entry.prunable_reason})"
        if (entry.prunable and entry.prunable_reason)
        else ("prunable=true" if entry.prunable else "prunable=false")
    )
    issue = "" if entry.issue is None else str(entry.issue)
    return [entry.path, branch, issue, str(entry.ahead), dirty, locked, prunable]


@worktrees_app.command("status")
@dry_run_class("no-external-request")
def worktrees_status(
    repo_dir: Annotated[
        Path | None,
        typer.Option("--repo-dir", "-r", help=HELP.repos.worktrees_repo_dir),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.repos.worktrees_json),
    ] = False,
) -> None:
    """List every worktree with commits ahead of main, dirty-path count, and flags."""
    root = (repo_dir or find_repo_root()).resolve()
    entries = inventory_worktrees(root)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        payload = [e.model_dump() for e in entries]
        emit_serialized(payload, resolved)
        return

    rows = [_format_worktree_table_row(e) for e in entries]
    print_table(
        title="Git Worktrees",
        columns=[
            ("Worktree", "cyan"),
            ("Branch", "green"),
            ("Issue", "cyan"),
            ("Ahead", "magenta"),
            ("Dirty", "yellow"),
            ("Locked", "red"),
            ("Prunable", "dim"),
        ],
        rows=rows,
    )


def _render_prune_item(item: Any) -> None:
    """Render a single prune outcome message."""
    size = "" if item.size_bytes is None else format_bytes(item.size_bytes)
    if item.status == "removed":
        print_success(f"removed {item.path}" + (f" ({size})" if size else ""), prefix=False)
    elif item.status in {"would remove", "would check"}:
        detail = ", ".join(part for part in (item.reason, size) if part)
        print_info(f"{item.status} {item.path} ({detail})", prefix=False)
    elif item.status == "refused":
        print_warning(f"refused {item.path}: {item.reason}", prefix=False)
    else:
        print_error(f"failed to remove {item.path}: {item.reason}", prefix=False)


def _render_prune_report(report: Any, *, dry_run: bool, confirm: bool) -> None:
    """Print a prune report as the table output of the command."""
    from devops_cli.dry_run.requests import PlannedRequest, render_request_plan

    for item in report.items:
        _render_prune_item(item)
    if dry_run:
        plan: list[PlannedRequest] = []
        for line in report.requests:
            method, _, target = line.partition(" ")
            plan.append(PlannedRequest(method, target))
        render_request_plan(
            MESSAGES.repos.worktrees_prune_heading,
            plan,
            MESSAGES.repos.worktrees_prune_dry_run_notes,
        )
    elif confirm:
        print_info(
            MESSAGES.repos.worktrees_prune_done.format(
                removed=report.removed_count,
                refused=report.refused_count,
                failed=report.failed_count,
                size=format_bytes(report.total_bytes),
            ),
            prefix=False,
        )
    else:
        would_remove = len([i for i in report.items if i.status == "would remove"])
        print_info(
            MESSAGES.repos.worktrees_prune_preview.format(
                would_remove=would_remove,
                refused=report.refused_count,
                size=format_bytes(report.total_bytes),
            ),
            prefix=False,
        )


def _claimed(report: WorktreeAddReport, *, origin: str | None, dry_run: bool) -> WorktreeAddReport:
    """The report with the claim of the issue for an agent (#2910): the claim runs after the
    worktree exists and never stops the command. A dry run lists the requests of the claim and
    makes none. An origin that is no GitHub repository has no roadmap to claim on."""
    if origin is None:
        return report
    if dry_run:
        lines = claim_request_lines(origin, report.issue)
        return report.model_copy(update={"requests": [*report.requests, *lines]})
    error = claim_as_agent(origin, report.issue)
    return report.model_copy(update={"claimed": error is None, "claim_error": error})


def _render_claim(report: WorktreeAddReport) -> None:
    """Print the claim of the issue after the worktree: a warning when it was not made."""
    if report.claim_error:
        print_warning(
            MESSAGES.repos.worktrees_add_not_claimed.format(
                issue=report.issue, reason=report.claim_error
            ),
            prefix=False,
        )
    elif report.claimed:
        print_info(MESSAGES.repos.worktrees_add_claimed.format(issue=report.issue), prefix=False)


def _render_add_report(report: Any) -> None:
    """Print what `add` did, or the commands that its dry run lists."""
    from devops_cli.dry_run.requests import PlannedRequest, render_request_plan

    if report.reclaim_error:
        print_warning(
            MESSAGES.repos.worktrees_add_not_reclaimed.format(reason=report.reclaim_error),
            prefix=False,
        )
    if report.status == "took over":
        print_success(
            MESSAGES.repos.worktrees_add_took_over.format(
                path=report.path, branch=report.branch, commits=report.commits
            ),
            prefix=False,
        )
        return
    if report.status == "created":
        print_success(
            MESSAGES.repos.worktrees_add_created.format(path=report.path, branch=report.branch),
            prefix=False,
        )
        return
    plan = [PlannedRequest(*line.partition(" ")[::2]) for line in report.requests]
    render_request_plan(
        MESSAGES.repos.worktrees_add_heading, plan, MESSAGES.repos.worktrees_add_dry_run_notes
    )


@worktrees_app.command("add")
def worktrees_add(
    issue: Annotated[
        int,
        typer.Argument(min=1, help=HELP.repos.worktrees_add_issue),
    ],
    branch_type: Annotated[
        str | None,
        typer.Option("--type", help=HELP.repos.worktrees_add_type),
    ] = None,
    slug: Annotated[
        str | None,
        typer.Option("--slug", help=HELP.repos.worktrees_add_slug),
    ] = None,
    repo_dir: Annotated[
        Path | None,
        typer.Option("--repo-dir", "-r", help=HELP.repos.worktrees_repo_dir),
    ] = None,
    reclaim: Annotated[
        bool,
        typer.Option("--reclaim/--no-reclaim", help=HELP.repos.worktrees_add_reclaim),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.repos.worktrees_json),
    ] = False,
) -> None:
    """Create the worktree of an issue on <type>/<issue>-<slug> at the fetched origin/main.

    The command first removes the worktrees of merged pull requests, as prune --confirm does,
    because a merged worktree still holds its issue. Then it refuses an issue that a worktree,
    the standard directory or a pushed branch of origin already holds. A pushed branch whose
    commits past origin/main all have the App as author is a staged branch: the command adds the
    worktree on it and takes --type and --slug from it. After the worktree exists, the command
    claims the issue for an agent with the label owner/agent. It only warns if the claim fails.
    """
    is_plan = dry_run or is_dry_run()
    if is_plan and (branch_type is None or slug is None):
        raise typer.BadParameter(MESSAGES.repos.worktrees_add_dry_run_needs_options)
    if branch_type is not None and branch_type not in CONST_BRANCH_TYPES:
        raise typer.BadParameter(
            MESSAGES.repos.worktrees_add_bad_type.format(
                type=branch_type, types=", ".join(CONST_BRANCH_TYPES)
            ),
            param_hint="--type",
        )
    if slug is not None and not is_valid_slug(slug):
        raise typer.BadParameter(
            MESSAGES.repos.worktrees_add_bad_slug.format(slug=slug), param_hint="--slug"
        )
    root = (repo_dir or find_repo_root()).resolve()
    resolved = resolve_format(output_format, json_output=json_output)
    reclaimed = reclaim_merged_worktrees(root, dry_run=is_plan) if reclaim else ReclaimResult()
    if resolved == CONST_OUTPUT_FORMAT_TABLE:
        # Each removal is shown before a later refusal can hide it.
        for item in reclaimed.removed:
            _render_prune_item(item)
    report = _claimed(
        add_worktree(
            root, issue=issue, type_=branch_type, slug=slug, dry_run=is_plan, reclaim=reclaimed
        ),
        origin=get_repo_origin_name(root),
        dry_run=is_plan,
    )

    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(), resolved)
    else:
        _render_add_report(report)
        _render_claim(report)


@worktrees_app.command("prune")
@dry_run_class("request-plan")
def worktrees_prune(
    repo_dir: Annotated[
        Path | None,
        typer.Option("--repo-dir", "-r", help=HELP.repos.worktrees_repo_dir),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help=HELP.repos.worktrees_force),
    ] = False,
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help=HELP.repos.worktrees_confirm),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help=HELP.options.dry_run),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.repos.worktrees_json),
    ] = False,
) -> None:
    """Remove the worktrees whose tip heads a merged pull request; preview unless --confirm."""
    is_plan = dry_run or is_dry_run()
    if is_plan and confirm:
        print_error(MESSAGES.repos.worktrees_dry_run_confirm)
        raise typer.Exit(1)
    root = (repo_dir or find_repo_root()).resolve()
    entries = inventory_worktrees(root)
    origin = get_repo_origin_name(root)
    if is_plan:
        report = plan_prune(entries, repo=origin, force=force)
    else:
        report = prune_worktrees(root, entries, repo=origin, force=force, confirm=confirm)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(), resolved)
    else:
        _render_prune_report(report, dry_run=is_plan, confirm=confirm)
    if report.failed_count:
        raise typer.Exit(1)
