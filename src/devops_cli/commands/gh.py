"""GitHub Views, Projects, Milestones, and Labels management command group."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.commands.pr import app as pr_app
from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.env import ENV_GITHUB_TOKEN
from devops_cli.config.settings import get_keyring_secret
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.github.client import GhCliClient, GitHubClient
from devops_cli.github.issues import (
    audit_issues_triage,
    create_repository_issue,
    get_issues_summary,
    get_repository_issues,
)
from devops_cli.github.labels import (
    audit_repository_labels,
    load_label_specs,
    sync_repository_labels,
)
from devops_cli.github.milestones import (
    calculate_milestone_progress,
    close_repository_milestone,
    extract_roadmap_milestones,
    sync_repository_milestones,
)
from devops_cli.github.pages import (
    get_pages_builds,
    get_pages_status,
    request_pages_build,
    verify_pages_configuration,
)
from devops_cli.github.projects import (
    audit_project_drift,
    audit_remote_project_views,
    link_project_to_repository,
    list_remote_projects,
    load_project_template,
    parse_tasks_to_project_items,
    sync_remote_project,
    sync_remote_project_views,
)
from devops_cli.lang import HELP
from devops_cli.output import (
    print,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_table,
    print_warning,
)

app = new_typer(help=HELP.gh.app, no_args_is_help=True)
labels_app = new_typer(help=HELP.gh.labels_app, no_args_is_help=True)
milestones_app = new_typer(help=HELP.gh.milestones_app, no_args_is_help=True)
project_app = new_typer(help=HELP.gh.project_app, no_args_is_help=True)
views_app = new_typer(help=HELP.gh.views_app, no_args_is_help=True)
pages_app = new_typer(help=HELP.gh.pages_app, no_args_is_help=True)
issues_app = new_typer(help=HELP.gh.issues_app, no_args_is_help=True)

app.add_typer(labels_app, name="labels")
app.add_typer(milestones_app, name="milestones")
app.add_typer(project_app, name="project")
app.add_typer(views_app, name="views")
app.add_typer(pages_app, name="pages")
app.add_typer(issues_app, name="issues")
app.add_typer(pr_app, name="pr")


def _resolve_repo(repo: str | None = None) -> str:
    """Resolve target repository string or discover from git origin."""
    target = repo or get_repo_origin_name()
    return target or "unknown/repo"


def _resolve_github_token() -> str | None:
    """Resolve GitHub authentication token from Keyring, environment, or gh CLI."""
    for key in ("github.token", "github_token", "github"):
        val = get_keyring_secret(key)
        if val:
            return val
    import os

    for env_var in (ENV_GITHUB_TOKEN, "GITHUB_TOKEN", "GH_TOKEN"):
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    res = run_subprocess([CONST_GH_CLI, "auth", "token"], check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    return None


def _get_github_client() -> GitHubClient | None:
    """Construct an authenticated GitHub client if token is available."""
    token = _resolve_github_token()
    if not token:
        return None
    try:
        return GitHubClient(token)
    except Exception:
        return None


def _get_repo_labels(repo: str | None = None) -> list[dict[str, Any]]:
    """Retrieve repository labels via gh CLI or GitHubClient."""
    target_repo = _resolve_repo(repo)
    cmd = [CONST_GH_CLI, "label", "list", "--json", "name,color,description"]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    client = _get_github_client()
    if client and target_repo != "unknown/repo":
        try:
            return client.get_labels(target_repo)
        except Exception:
            pass
    return []


def _get_repo_milestones(repo: str | None = None, state: str = "all") -> list[dict[str, Any]]:
    """Retrieve repository milestones via GitHubClient or gh api."""
    target_repo = _resolve_repo(repo)
    client = _get_github_client()
    if client and target_repo != "unknown/repo":
        try:
            return client.get_milestones(target_repo, state=state)
        except Exception:
            pass

    cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{target_repo}/milestones?state={state}&per_page=100",
    ]
    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            raw = json.loads(res.stdout)
            return [
                {
                    "title": m.get("title", ""),
                    "number": m.get("number", 0),
                    "state": m.get("state", "open"),
                    "description": m.get("description", "") or "",
                    "open_issues": m.get("open_issues", 0),
                    "closed_issues": m.get("closed_issues", 0),
                    "due_on": m.get("due_on"),
                }
                for m in raw
                if isinstance(m, dict)
            ]
        except json.JSONDecodeError:
            pass
    return []


def _get_repo_prs(repo: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    """Retrieve open pull requests for taxonomy auditing."""
    cmd = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        str(limit),
        "--json",
        "number,title,labels",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass
    return []


# =============================================================================
# Labels Subcommands
# =============================================================================


@labels_app.command("list")
def list_labels(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """List all labels defined in the remote repository."""
    labels = _get_repo_labels(repo)
    if not labels:
        print_info("No remote repository labels found or gh CLI not configured.")
        return

    columns = ["Label Name", "Color", "Description"]
    rows = [
        [
            f"#{lbl.get('color', '')} {lbl.get('name', '')}",
            lbl.get("color", ""),
            lbl.get("description", "") or "—",
        ]
        for lbl in labels
    ]
    print_table("Repository Labels", columns, rows)


@labels_app.command("sync")
def sync_labels(
    file: Annotated[
        Path,
        typer.Option("--file", "-f", help="Path to declarative labels.yml file"),
    ] = Path(".github/labels.yml"),
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview label reconciliation without making changes"),
    ] = False,
) -> None:
    """Synchronize repository labels against the declarative YAML schema."""
    target_repo = _resolve_repo(repo)
    try:
        desired = load_label_specs(file)
    except Exception as exc:
        print_error(f"Failed to load labels schema: {exc}")
        raise typer.Exit(1) from exc

    client = _get_github_client() or GhCliClient(target_repo)
    result = sync_repository_labels(client, target_repo, desired, dry_run=dry_run)
    mode_text = "[yellow][DRY RUN][/yellow] " if result.dry_run else ""
    print_success(
        f"{mode_text}Label sync complete for {target_repo}: "
        f"{result.created_count} to create, {result.updated_count} to update, "
        f"{result.unchanged_count} unchanged."
    )


@labels_app.command("audit")
def audit_labels(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Audit open pull requests for mandatory type/ and scope/ taxonomy labels."""
    prs = _get_repo_prs(repo)
    findings = audit_repository_labels(prs)

    if not findings:
        print_success("All open pull requests comply with taxonomy labeling standards!")
        return

    columns = ["PR #", "PR Title", "Taxonomy Issue"]
    rows = [[f"#{f.pr_number}", f.title, f.issue] for f in findings]
    print_table("Pull Request Taxonomy Audit Findings", columns, rows)


# =============================================================================
# Milestones Subcommands
# =============================================================================


@milestones_app.command("list")
def list_milestones(
    state: Annotated[str, typer.Option("--state", "-s", help="Milestone state filter")] = "all",
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """List repository milestones and track issue completion rates."""
    milestones = _get_repo_milestones(repo, state=state)
    if not milestones:
        print_info("No milestones found in repository.")
        return

    columns = ["Milestone", "State", "Progress", "Open", "Closed", "Due Date"]
    rows: list[list[str]] = []
    for m in milestones:
        prog = calculate_milestone_progress(m)
        rows.append(
            [
                prog.title,
                prog.state.upper(),
                f"{prog.percent_complete:.1f}%",
                str(prog.open_issues),
                str(prog.closed_issues),
                prog.due_on or "—",
            ]
        )
    print_table("Release Milestones", columns, rows)


@milestones_app.command("sync")
def sync_milestones(
    roadmap: Annotated[
        Path,
        typer.Option("--roadmap", "-r", help="Path to docs/ROADMAP.md file"),
    ] = Path("docs/ROADMAP.md"),
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Simulate milestone extraction without creating remote records"
        ),
    ] = False,
) -> None:
    """Extract release milestones from ROADMAP.md and sync to repository."""
    target_repo = _resolve_repo(repo)
    try:
        desired = extract_roadmap_milestones(roadmap)
    except Exception as exc:
        print_error(f"Failed to extract milestones from roadmap: {exc}")
        raise typer.Exit(1) from exc

    client = _get_github_client() or GhCliClient(target_repo)
    result = sync_repository_milestones(client, target_repo, desired, dry_run=dry_run)
    mode_text = "[yellow][DRY RUN][/yellow] " if result.dry_run else ""
    print_success(
        f"{mode_text}Milestone synchronization for {target_repo}: "
        f"{result.created_count} to create, {result.existing_count} existing."
    )


@milestones_app.command("status")
def status_milestone(
    name: Annotated[str, typer.Argument(help="Milestone version or title (e.g. v0.2.11)")],
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Inspect detailed progress and issue health for a specific milestone."""
    milestones = _get_repo_milestones(repo)
    matched = next((m for m in milestones if m.get("title") == name), None)
    if not matched:
        print_error(f"Milestone '{name}' not found in repository.")
        raise typer.Exit(1)

    prog = calculate_milestone_progress(matched)
    print_panel(
        f"Title: {prog.title}\n"
        f"State: {prog.state.upper()}\n"
        f"Completion: {prog.percent_complete:.1f}%\n"
        f"Open Issues / PRs: {prog.open_issues}\n"
        f"Closed Issues / PRs: {prog.closed_issues}\n"
        f"Total Tracked: {prog.total_issues}\n"
        f"Due Date: {prog.due_on or 'Not specified'}",
        title=f"Milestone Status — {prog.title}",
    )


def _close_milestone_gh_cli(target_repo: str, name: str) -> bool:
    """Close milestone using gh CLI when GitHubClient is unavailable."""
    milestones = _get_repo_milestones(target_repo, state="all")
    target = name.strip()
    candidates = {target, target.lstrip("v"), f"v{target.lstrip('v')}"}
    matched = next((m for m in milestones if m.get("title") in candidates), None)
    if matched and "number" in matched:
        num = matched["number"]
        cmd = [
            CONST_GH_CLI,
            "api",
            "-X",
            "PATCH",
            f"repos/{target_repo}/milestones/{num}",
            "-f",
            "state=closed",
        ]
        proc = run_subprocess(cmd, check=False)
        return proc.returncode == 0
    return False


@milestones_app.command("close", help=HELP.gh.milestones_close)
def close_milestone(
    name: Annotated[str, typer.Argument(help="Milestone version or title (e.g. v0.2.11)")],
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Close a repository release milestone matching the given version or title."""
    target_repo = repo or _resolve_repo()
    client = _get_github_client()
    success = (
        close_repository_milestone(client, target_repo, name)
        if client
        else _close_milestone_gh_cli(target_repo, name)
    )

    if success:
        print_success(f"Successfully closed milestone '{name}' in {target_repo}.")
    else:
        print_error(
            f"Failed to close milestone '{name}' in {target_repo} (not found or permission denied)."
        )
        raise typer.Exit(1)


# =============================================================================
# Project Subcommands
# =============================================================================


@project_app.command("status")
def status_project(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
) -> None:
    """Inspect the declarative GitHub Projects v2 template structure and views."""
    template = load_project_template(template_file)
    print_panel(
        f"Project Name: {template.name}\n"
        f"Short Name: {template.short_name}\n"
        f"Custom Fields ({len(template.fields)}): {', '.join(f.name for f in template.fields)}\n"
        f"Configured Views ({len(template.views)}): {', '.join(v.name for v in template.views)}",
        title="GitHub Projects v2 Configuration",
    )


@project_app.command("sync", help=HELP.gh.project_sync)
def sync_project(
    task_file: Annotated[
        Path,
        typer.Option("--task-file", "-f", help="Path to docs/agent/task.md"),
    ] = Path("docs/agent/task.md"),
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run", help="Preview task card items without remote mutations"
        ),
    ] = False,
    reconcile_fields: Annotated[
        bool,
        typer.Option(
            "--reconcile-fields/--no-reconcile-fields",
            help=HELP.gh.reconcile_fields,
        ),
    ] = True,
) -> None:
    """Synchronize task.md lifecycle items into GitHub Projects v2 status."""
    items = parse_tasks_to_project_items(task_file)
    counts: dict[str, int] = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1

    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    target_repo = repo or _resolve_repo()
    owner = target_repo.split("/")[0] if "/" in target_repo else "@me"
    template = load_project_template(template_file)

    try:
        res = sync_remote_project(
            owner=owner,
            repo=target_repo,
            template=template,
            items=items,
            dry_run=dry_run,
            reconcile_fields=reconcile_fields,
        )
        mode_text = "[yellow][DRY RUN][/yellow] " if res.dry_run else ""
        link_text = " linked to repository" if res.linked else ""
        print_success(
            f"{mode_text}Project '{res.project_title}' (#{res.project_number}){link_text}: "
            f"synchronized {res.items_synced} items ({summary}). "
            f"Provisioned fields: {', '.join(res.fields_provisioned) or 'all up-to-date'}."
        )
    except Exception as exc:
        print_warning(f"Remote project sync skipped or failed: {exc}")
        print_info(f"Local tasks parsed: {len(items)} items ({summary}).")


@project_app.command("reconcile", help=HELP.gh.project_reconcile)
def reconcile_project_cmd(
    project_number: Annotated[
        int | None,
        typer.Option("--project-number", "-n", help="GitHub Projects v2 board number"),
    ] = None,
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview field reconciliation without mutations"),
    ] = False,
) -> None:
    """Reconcile custom fields (Status, Priority, Category, Value, Effort) on project items."""
    from devops_cli.github.projects import (
        find_remote_project,
        load_project_template,
        reconcile_project_custom_fields,
    )

    target_repo = repo or _resolve_repo()
    owner = target_repo.split("/")[0] if "/" in target_repo else "@me"
    proj_num = project_number
    if not proj_num:
        template = load_project_template()
        matched = find_remote_project(owner, template.name)
        if not matched and template.short_name:
            matched = find_remote_project(owner, template.short_name)
        proj_num = int(matched.get("number", 1)) if matched else 1

    mode_text = "[yellow][DRY RUN][/yellow] " if dry_run else ""
    try:
        res = reconcile_project_custom_fields(
            owner=owner,
            repo=target_repo,
            project_number=proj_num,
            dry_run=dry_run,
        )
        print_success(
            f"{mode_text}Reconciled project #{proj_num} custom fields: "
            f"{res['items_reconciled']}/{res['items_evaluated']} items updated."
        )
    except Exception as exc:
        print_error(f"Failed to reconcile project #{proj_num}: {exc}")
        raise typer.Exit(1)


@project_app.command("link", help=HELP.gh.project_link)
def link_project(
    project_number: Annotated[int, typer.Argument(help="GitHub Projects v2 board number")],
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Link a GitHub Projects v2 board to the repository."""
    target_repo = repo or _resolve_repo()
    owner = target_repo.split("/")[0] if "/" in target_repo else "@me"
    repo_name = target_repo.split("/")[1] if "/" in target_repo else target_repo
    ok = link_project_to_repository(project_number, owner, repo_name)
    if ok:
        print_success(f"Linked project #{project_number} to {target_repo}.")
    else:
        print_error(f"Failed to link project #{project_number} to {target_repo}.")
        raise typer.Exit(1)


@project_app.command("list", help=HELP.gh.project_list)
def list_projects(
    owner: Annotated[
        str | None, typer.Option("--owner", "-o", help="Target user or organization")
    ] = None,
) -> None:
    """List available GitHub Projects v2 boards."""
    resolved_owner = owner or _resolve_repo().split("/")[0]
    projects = list_remote_projects(resolved_owner)
    if not projects:
        print_info(f"No GitHub Projects v2 boards found for owner '{resolved_owner}'.")
        return
    columns = ["#", "Project Title", "State", "ID", "URL"]
    rows = [[str(p["number"]), p["title"], p["state"].upper(), p["id"], p["url"]] for p in projects]
    print_table(f"GitHub Projects v2 Boards ({resolved_owner})", columns, rows)


@project_app.command("audit", help=HELP.gh.project_audit)
def audit_project(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Audit project board health and alignment against standardized template."""
    target_repo = repo or _resolve_repo()
    owner = target_repo.split("/")[0] if "/" in target_repo else "@me"
    repo_name = target_repo.split("/")[1] if "/" in target_repo else target_repo
    template = load_project_template(template_file)
    res = audit_project_drift(owner, repo_name, template)
    if not res.get("project_found"):
        print_warning(f"No active project board found for repository '{target_repo}'.")
        return
    proj_num = res.get("project_number")
    status_str = (
        "[green]COMPLIANT[/green]"
        if res.get("views_compliant")
        else "[yellow]DRIFT DETECTED[/yellow]"
    )
    print_panel(
        f"Project #{proj_num} Status: {status_str}\n"
        f"Matching Views: {', '.join(res.get('matching_views', [])) or 'none'}\n"
        f"Missing Views: {', '.join(res.get('missing_views', [])) or 'none'}",
        title="Project Board Audit",
    )


@project_app.command("template")
def show_template(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
) -> None:
    """Display the raw GitHub Projects v2 declarative JSON template."""
    content = template_file.read_text(encoding="utf-8")
    print(content)


# =============================================================================
# Views Subcommands
# =============================================================================


@views_app.command("list")
def list_views(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
) -> None:
    """List all standardized GitHub Projects v2 views configured for this workspace."""
    template = load_project_template(template_file)
    columns = ["View Name", "Layout", "Group By", "Visible Fields", "Description"]
    rows = [
        [
            v.name,
            v.layout.upper(),
            v.group_by or "—",
            ", ".join(v.visible_fields),
            v.description,
        ]
        for v in template.views
    ]
    print_table("GitHub Projects v2 Standardized Views", columns, rows)


@views_app.command("spec")
def spec_views(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
) -> None:
    """Output JSON schema specification for all configured project views."""
    template = load_project_template(template_file)
    views_dicts = [v.model_dump() for v in template.views]
    print(json.dumps(views_dicts, indent=2))


def _display_issues_saved_views(target_repo: str) -> None:
    """Output reference URLs for GitHub Issues saved views."""
    columns = ["View Name", "Issues Filter Query", "Direct Link"]
    views_specs = [
        ("Sprint Kanban", "is:issue state:open milestone:current"),
        (
            "Triage & Quality Table",
            "is:issue state:open label:status/triage,status/blocked,type/bug",
        ),
        ("Roadmap Timeline", "is:issue state:open sort:milestone-desc"),
        ("Value vs Effort Priority Matrix", "is:issue state:open sort:priority-desc"),
    ]
    rows = [
        [
            name,
            query,
            f"https://github.com/{target_repo}/issues?q={urllib.parse.quote_plus(query)}",
        ]
        for name, query in views_specs
    ]
    print_table(
        f"Repository Issues Views (Save via https://github.com/{target_repo}/issues/views)",
        columns,
        rows,
    )


@views_app.command("sync", help=HELP.gh.views_sync)
def sync_views(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Synchronize standardized views with remote GitHub Projects v2 board."""
    target_repo = repo or _resolve_repo()
    owner = target_repo.split("/")[0] if "/" in target_repo else "@me"
    repo_name = target_repo.split("/")[1] if "/" in target_repo else target_repo
    template = load_project_template(template_file)

    try:
        res = sync_remote_project_views(owner, repo_name, template)
        proj_num = res.get("project_number")
        if proj_num:
            print_success(
                f"Project #{proj_num} views synchronized: "
                f"{len(res.get('existing', []))} existing, {len(res.get('created', []))} created "
                f"({', '.join(res.get('views', []))})."
            )
        else:
            print_warning(f"Could not sync views: {res.get('status', 'Project not found')}")
    except Exception as exc:
        print_warning(f"Views sync skipped or failed: {exc}")

    _display_issues_saved_views(target_repo)


@views_app.command("audit", help=HELP.gh.views_audit)
def audit_views(
    template_file: Annotated[
        Path,
        typer.Option("--template", "-t", help="Path to project template JSON"),
    ] = Path(".github/project-template.json"),
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Audit remote project views against standardized view template specifications."""
    target_repo = repo or _resolve_repo()
    owner = target_repo.split("/")[0] if "/" in target_repo else "@me"
    repo_name = target_repo.split("/")[1] if "/" in target_repo else target_repo
    template = load_project_template(template_file)
    res = audit_remote_project_views(owner, repo_name, template)
    if not res.get("project_number"):
        print_warning(f"No linked project board found for repository '{target_repo}'.")
        return
    columns = ["View Name", "Required", "Remote Status"]
    matching = set(res.get("matching_views", []))
    rows = [
        [
            v.name,
            "YES",
            "[green]FOUND[/green]" if v.name in matching else "[red]MISSING[/red]",
        ]
        for v in template.views
    ]
    print_table(f"Project Views Compliance (Project #{res.get('project_number')})", columns, rows)


# =============================================================================
# GitHub Pages Subcommands
# =============================================================================


@pages_app.command("status", help=HELP.gh.pages_status)
def pages_status_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Inspect GitHub Pages deployment status, URL, branch, and HTTPS enforcement."""
    target_repo = repo or _resolve_repo()
    info = get_pages_status(target_repo)
    if not info:
        print_warning(
            f"Repository '{target_repo}' does not have GitHub Pages enabled or published."
        )
        return
    https_badge = "[green]ENFORCED[/green]" if info.https_enforced else "[yellow]DISABLED[/yellow]"
    print_panel(
        f"Deployment Status: [bold cyan]{info.status.upper()}[/bold cyan]\n"
        f"Site URL: [link={info.html_url}]{info.html_url}[/link]\n"
        f"Source Branch: {info.branch} (path: {info.path})\n"
        f"Build Type: {info.build_type}\n"
        f"HTTPS Enforced: {https_badge}\n"
        f"Custom Domain: {info.cname or '—'}",
        title=f"GitHub Pages Status ({target_repo})",
    )


@pages_app.command("builds", help=HELP.gh.pages_builds)
def pages_builds_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of builds to retrieve")] = 5,
) -> None:
    """List recent GitHub Pages build history and durations."""
    target_repo = repo or _resolve_repo()
    builds = get_pages_builds(target_repo, limit=limit)
    if not builds:
        print_info(f"No recent GitHub Pages builds found for '{target_repo}'.")
        return
    columns = ["Commit", "Status", "Duration", "Created At", "Error"]
    rows = [
        [
            b.commit[:7] if b.commit else "—",
            b.status.upper(),
            f"{b.duration_ms / 1000:.1f}s" if b.duration_ms else "—",
            b.created_at or "—",
            b.error_message or "—",
        ]
        for b in builds
    ]
    print_table(f"GitHub Pages Build History ({target_repo})", columns, rows)


@pages_app.command("build", help=HELP.gh.pages_build)
def pages_build_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Trigger a new deployment build for GitHub Pages."""
    target_repo = repo or _resolve_repo()
    ok = request_pages_build(target_repo)
    if ok:
        print_success(f"Successfully requested GitHub Pages build for '{target_repo}'.")
    else:
        print_error(f"Failed to request GitHub Pages build for '{target_repo}'.")
        raise typer.Exit(1)


@pages_app.command("verify", help=HELP.gh.pages_verify)
def pages_verify_cmd(
    root_dir: Annotated[
        Path,
        typer.Option("--dir", "-d", help="Path to project root directory"),
    ] = Path("."),
) -> None:
    """Verify local repository readiness for GitHub Pages publishing."""
    valid, diagnostics = verify_pages_configuration(root_dir)
    for diag in diagnostics:
        if diag.startswith("✓"):
            print_success(diag)
        else:
            print_error(diag)
    if not valid:
        raise typer.Exit(1)
    print_success("GitHub Pages local configuration is 100% compliant.")


# =============================================================================
# GitHub Issues Subcommands
# =============================================================================


@issues_app.command("list", help=HELP.gh.issues_list)
def issues_list_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
    state: Annotated[
        str, typer.Option("--state", "-s", help="Issue state: open, closed, all")
    ] = "open",
    milestone: Annotated[
        str | None, typer.Option("--milestone", "-m", help="Filter by milestone")
    ] = None,
    label: Annotated[str | None, typer.Option("--label", "-l", help="Filter by label")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Max issues to return")] = 30,
) -> None:
    """List repository issues with milestone, taxonomy labels, and status."""
    target_repo = repo or _resolve_repo()
    issues = get_repository_issues(
        target_repo, state=state, milestone=milestone, label=label, limit=limit
    )
    if not issues:
        print_info(f"No {state} issues found in '{target_repo}'.")
        return
    columns = ["#", "Title", "Milestone", "Labels", "Assignees"]
    rows = [
        [
            f"#{iss.number}",
            iss.title[:50] + ("..." if len(iss.title) > 50 else ""),
            iss.milestone or "—",
            ", ".join(iss.labels[:3]) or "—",
            ", ".join(iss.assignees) or "—",
        ]
        for iss in issues
    ]
    print_table(f"Repository Issues ({target_repo})", columns, rows)


@issues_app.command("create", help=HELP.gh.issues_create)
def issues_create_cmd(
    title: Annotated[str, typer.Option("--title", "-t", help="Issue title")],
    body: Annotated[str, typer.Option("--body", "-b", help="Issue description")] = "",
    milestone: Annotated[
        str | None, typer.Option("--milestone", "-m", help="Target milestone")
    ] = None,
    label: Annotated[
        list[str] | None, typer.Option("--label", "-l", help="Taxonomy label (repeatable)")
    ] = None,
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Create a new issue linking milestone and taxonomy labels."""
    target_repo = repo or _resolve_repo()
    created = create_repository_issue(
        target_repo,
        title=title,
        body=body,
        milestone=milestone,
        labels=label,
    )
    print_success(f"Created issue #{created.number}: '{created.title}' ({created.url or 'local'})")


@issues_app.command("triage", help=HELP.gh.issues_triage)
def issues_triage_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Audit open issues for mandatory taxonomy labels and milestone linkage."""
    target_repo = repo or _resolve_repo()
    audit = audit_issues_triage(target_repo)
    columns = ["Metric", "Value", "Violating Issues"]
    rows = [
        ["Total Open Issues", str(audit.total_open), "—"],
        ["Taxonomy Compliant", f"{audit.valid_count} ({audit.compliance_rate}%)", "—"],
        [
            "Missing type/*",
            str(len(audit.issues_missing_type)),
            ", ".join(f"#{n}" for n in audit.issues_missing_type) or "None",
        ],
        [
            "Missing scope/*",
            str(len(audit.issues_missing_scope)),
            ", ".join(f"#{n}" for n in audit.issues_missing_scope) or "None",
        ],
        [
            "Missing priority/*",
            str(len(audit.issues_missing_priority)),
            ", ".join(f"#{n}" for n in audit.issues_missing_priority) or "None",
        ],
        [
            "Missing Milestone",
            str(len(audit.issues_missing_milestone)),
            ", ".join(f"#{n}" for n in audit.issues_missing_milestone) or "None",
        ],
    ]
    print_table(f"GitHub Issues Triage & Taxonomy Audit ({target_repo})", columns, rows)
    if audit.valid_count < audit.total_open:
        print_warning(
            "Triage audit detected issues missing required taxonomy labels or milestone linkage."
        )


@issues_app.command("status", help=HELP.gh.issues_status)
def issues_status_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help="Target repository")] = None,
) -> None:
    """Display aggregated issue counts by priority, type, and milestone."""
    target_repo = repo or _resolve_repo()
    summary = get_issues_summary(target_repo)
    columns = ["Category", "Breakdown"]
    p_str = ", ".join(f"{k}: {v}" for k, v in sorted(summary.get("by_priority", {}).items()))
    t_str = ", ".join(f"{k}: {v}" for k, v in sorted(summary.get("by_type", {}).items()))
    m_str = ", ".join(f"{k}: {v}" for k, v in sorted(summary.get("by_milestone", {}).items()))
    rows = [
        ["Total Open", str(summary.get("total_open", 0))],
        ["By Priority", p_str or "none"],
        ["By Type", t_str or "none"],
        ["By Milestone", m_str or "none"],
    ]
    print_table(f"GitHub Issues Status Summary ({target_repo})", columns, rows)
