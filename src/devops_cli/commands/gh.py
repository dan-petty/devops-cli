"""GitHub Views, Projects, Milestones, and Labels management command group."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.env import ENV_GITHUB_TOKEN
from devops_cli.config.settings import get_keyring_secret
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.github.client import GitHubClient
from devops_cli.github.labels import (
    audit_repository_labels,
    load_label_specs,
    sync_repository_labels,
)
from devops_cli.github.milestones import (
    calculate_milestone_progress,
    extract_roadmap_milestones,
    sync_repository_milestones,
)
from devops_cli.github.projects import (
    load_project_template,
    parse_tasks_to_project_items,
)
from devops_cli.lang import HELP
from devops_cli.output import (
    print,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_table,
)

app = new_typer(help=HELP.gh.app, no_args_is_help=True)
labels_app = new_typer(help=HELP.gh.labels_app, no_args_is_help=True)
milestones_app = new_typer(help=HELP.gh.milestones_app, no_args_is_help=True)
project_app = new_typer(help=HELP.gh.project_app, no_args_is_help=True)
views_app = new_typer(help=HELP.gh.views_app, no_args_is_help=True)

app.add_typer(labels_app, name="labels")
app.add_typer(milestones_app, name="milestones")
app.add_typer(project_app, name="project")
app.add_typer(views_app, name="views")


def _resolve_repo(repo: str | None) -> str:
    """Resolve target repository string or discover from git origin."""
    target = repo or get_repo_origin_name()
    return target or "unknown/repo"


def _get_github_client() -> GitHubClient | None:
    """Construct an authenticated GitHub client if token is available."""
    token = (
        get_keyring_secret("github.token")
        or get_keyring_secret("github_token")
        or get_keyring_secret("github")
    )
    if not token:
        import os

        token = (
            os.environ.get(ENV_GITHUB_TOKEN)
            or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
        )
    if not token:
        res = run_subprocess([CONST_GH_CLI, "auth", "token"], check=False, quiet=True)
        if res.returncode == 0 and res.stdout.strip():
            token = res.stdout.strip()
    if token:
        try:
            return GitHubClient(token)
        except Exception:
            return None
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

    client = _get_github_client()
    if not client:
        # Provide lightweight mock/wrapper client for local sync or dry runs
        class _GhCliLabelShim:
            def get_labels(self, r: str) -> list[dict[str, Any]]:
                return _get_repo_labels(repo)

            def create_label(self, r: str, name: str, color: str, description: str = "") -> None:
                cmd = [
                    CONST_GH_CLI,
                    "label",
                    "create",
                    name,
                    "--color",
                    color,
                    "--description",
                    description,
                ]
                if repo:
                    cmd.extend(["--repo", repo])
                run_subprocess(cmd, check=False)

            def edit_label(self, r: str, name: str, color: str, description: str = "") -> None:
                cmd = [
                    CONST_GH_CLI,
                    "label",
                    "edit",
                    name,
                    "--color",
                    color,
                    "--description",
                    description,
                ]
                if repo:
                    cmd.extend(["--repo", repo])
                run_subprocess(cmd, check=False)

        client = _GhCliLabelShim()  # type: ignore[assignment]

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

    client = _get_github_client()
    if not client:

        class _GhCliMilestoneShim:
            def get_milestones(self, r: str, state: str = "all") -> list[dict[str, Any]]:
                return _get_repo_milestones(r, state=state)

            def create_milestone(
                self,
                r: str,
                title: str,
                description: str = "",
                state: str = "open",
                due_on: Any = None,
            ) -> None:
                cmd = [
                    CONST_GH_CLI,
                    "api",
                    f"repos/{r}/milestones",
                    "-f",
                    f"title={title}",
                    "-f",
                    f"description={description}",
                    "-f",
                    f"state={state}",
                ]
                if due_on:
                    cmd.extend(["-f", f"due_on={due_on}"])
                run_subprocess(cmd, check=False)

        client = _GhCliMilestoneShim()  # type: ignore[assignment]

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


@project_app.command("sync")
def sync_project(
    task_file: Annotated[
        Path,
        typer.Option("--task-file", "-f", help="Path to docs/agent/task.md"),
    ] = Path("docs/agent/task.md"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview task card items without sending mutations"),
    ] = True,
) -> None:
    """Synchronize task.md lifecycle items into GitHub Projects v2 status."""
    items = parse_tasks_to_project_items(task_file)
    counts: dict[str, int] = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1

    mode_text = "[yellow][DRY RUN][/yellow] " if dry_run else ""
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    print_success(f"{mode_text}Parsed {len(items)} items from {task_file} ({summary}).")


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
