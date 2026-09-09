"""GitHub Pull Request management and governance command group."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import DEFAULT_PR_LIMIT, DEFAULT_PR_STATE
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
    print_warning,
)

app = new_typer(
    help=HELP.pr.app,
    no_args_is_help=True,
)


def _require_gh_cli() -> None:
    if not check_binary(CONST_GH_CLI):
        print_error(MESSAGES.pr.gh_cli_required, prefix=False)
        raise typer.Exit(1)


def _run_gh_pr_command(subcommand: str, number: int, repo: str | None = None) -> None:
    """Execute a GitHub PR subcommand (e.g. view, checks) for a PR number."""
    _require_gh_cli()
    cmd = [CONST_GH_CLI, "pr", subcommand, str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_subprocess(cmd, check=False)
    if res.returncode != 0:
        raise typer.Exit(res.returncode)


def _detect_active_release_branch() -> str | None:
    """Detect latest local/remote release branch (e.g. release/v0.2.0)."""
    res = run_subprocess(["git", "branch", "-a"], check=False, quiet=True)
    if res.returncode != 0:
        return None
    matches = re.findall(r"release/v\d+\.\d+\.\d+", res.stdout)
    if not matches:
        return None

    # Sort version strings semantically
    def _ver_key(v: str) -> tuple[int, ...]:
        clean = v.split("release/v")[-1]
        try:
            return tuple(int(x) for x in clean.split("."))
        except ValueError:
            return (0, 0, 0)

    sorted_releases = sorted(set(matches), key=_ver_key, reverse=True)
    return sorted_releases[0] if sorted_releases else None


# =============================================================================
# Command: devops pr list
# =============================================================================


@app.command("list")
def list_prs(
    state: Annotated[
        str,
        typer.Option("--state", "-s", help=HELP.pr.state_filter),
    ] = DEFAULT_PR_STATE,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help=HELP.options.limit),
    ] = DEFAULT_PR_LIMIT,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """List pull requests with base targeting and review status."""
    _require_gh_cli()
    cmd = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,state,headRefName,baseRefName,author,updatedAt,url",
    ]
    if repo:
        cmd.extend(["--repo", repo])

    res = run_subprocess(cmd, check=False)
    if res.returncode != 0:
        print_error(f"Failed to list PRs: {res.stderr}", prefix=False)
        raise typer.Exit(res.returncode)

    try:
        prs = json.loads(res.stdout) if res.stdout.strip() else []
    except json.JSONDecodeError:
        prs = []

    if not prs:
        print_warning(MESSAGES.pr.no_prs_found, prefix=False)
        return

    rows: list[list[str]] = []
    for pr in prs:
        number = str(pr.get("number", ""))
        title = str(pr.get("title", ""))
        head = str(pr.get("headRefName", ""))
        base = str(pr.get("baseRefName", ""))
        author_data = pr.get("author", {})
        if isinstance(author_data, dict):
            author = author_data.get("login", "")
        else:
            author = str(author_data)
        updated = str(pr.get("updatedAt", ""))[:10]
        url = str(pr.get("url", ""))

        rows.append([f"#{number}", title, head, base, author, updated, url])

    print_table(
        title=MESSAGES.pr.list_title.format(state=state),
        columns=[
            ("#", "right"),
            ("Title", "bold"),
            ("Branch", "cyan"),
            ("Base", "magenta"),
            ("Author", "dim"),
            ("Updated", "dim"),
            "URL",
        ],
        rows=rows,
    )


# =============================================================================
# Command: devops pr view
# =============================================================================


@app.command("view")
def view_pr(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """View details of a pull request."""
    _run_gh_pr_command("view", number, repo)


# =============================================================================
# Command: devops pr checks
# =============================================================================


@app.command("checks")
def pr_checks(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Check remote CI quality gate status on a pull request."""
    _run_gh_pr_command("checks", number, repo)


# =============================================================================
# Command: devops pr edit
# =============================================================================


@app.command("edit")
def edit_pr(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    base: Annotated[
        str | None,
        typer.Option("--base", "-B", help=HELP.pr.edit_base),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", "-t", help=HELP.pr.edit_title),
    ] = None,
    body: Annotated[
        str | None,
        typer.Option("--body", "-b", help=HELP.pr.edit_body),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Edit pull request base branch, title, or body."""
    _require_gh_cli()
    cmd = [CONST_GH_CLI, "pr", "edit", str(number)]
    if base:
        cmd.extend(["--base", base])
    if title:
        cmd.extend(["--title", title])
    if body:
        cmd.extend(["--body", body])
    if repo:
        cmd.extend(["--repo", repo])

    res = run_subprocess(cmd, check=False)
    if res.returncode != 0:
        raise typer.Exit(res.returncode)
    print_success(f"Successfully updated PR #{number}")


# =============================================================================
# Command: devops pr create
# =============================================================================


@app.command("create")
def create_pr(
    title: Annotated[str, typer.Option("--title", "-t", help=HELP.options.title)],
    body: Annotated[str, typer.Option("--body", "-b", help=HELP.options.body)] = "",
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            "-B",
            help=HELP.options.base_branch,
        ),
    ] = None,
    draft: Annotated[
        bool,
        typer.Option("--draft", "-d", help=HELP.options.draft),
    ] = False,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Create a pull request with automatic release branch target validation."""
    _require_gh_cli()
    target_base = base
    if not target_base:
        target_base = _detect_active_release_branch() or "main"

    cmd = [
        CONST_GH_CLI,
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--base",
        target_base,
    ]
    if draft:
        cmd.append("--draft")
    if repo:
        cmd.extend(["--repo", repo])

    res = run_subprocess(cmd, check=False)
    if res.returncode != 0:
        raise typer.Exit(res.returncode)
    print_success(f"Pull request created successfully targeting base [bold]{target_base}[/bold]")


# =============================================================================
# Command Group: devops pr threads
# =============================================================================

threads_app = new_typer(
    help=HELP.pr.threads_app,
    no_args_is_help=True,
)
app.add_typer(threads_app, name="threads")


def _render_threads_table(threads: list[Any]) -> None:
    """Render PR review threads as a rich table."""
    rows: list[list[str]] = []
    for t in threads:
        status = "[green]Resolved[/green]" if t.is_resolved else "[bold yellow]Open[/bold yellow]"
        loc = f"{t.path}:{t.line}" if t.line else t.path
        author = t.comments[0].author if t.comments else ""
        first_comment = (
            (t.comments[0].body[:50] + "...")
            if t.comments and len(t.comments[0].body) > 50
            else (t.comments[0].body if t.comments else "")
        )
        first_comment = first_comment.replace("\n", " ")
        rows.append([t.id, status, loc, author, first_comment])

    print_table(
        title="PR Review Discussion Threads",
        columns=["Thread ID", "Status", "Location", "Author", "First Comment"],
        rows=rows,
    )


@threads_app.command("list")
def list_threads(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.pr.target_repo)] = None,
    unresolved_only: Annotated[
        bool,
        typer.Option("--unresolved-only", "-u", help=HELP.pr.unresolved_only),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = "table",
) -> None:
    """List PR review discussion threads, file locations, and comments."""
    from devops_cli.core.repo import get_repo_origin_name
    from devops_cli.github.pr_threads import list_pr_review_threads

    target_repo = repo or get_repo_origin_name()
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.")
        raise typer.Exit(1)

    owner, repo_name = target_repo.split("/", 1)
    threads = list_pr_review_threads(owner, repo_name, number, unresolved_only=unresolved_only)

    if output_format == "json":
        from devops_cli.output import print as print_out

        print_out(json.dumps([t.model_dump() for t in threads], indent=2))
        return

    if not threads:
        msg = (
            "No unresolved review threads found."
            if unresolved_only
            else "No review threads found on PR."
        )
        print_success(msg)
        return

    _render_threads_table(threads)


@threads_app.command("reply")
def reply_thread(
    thread_id: Annotated[str, typer.Argument(help=HELP.pr.thread_id)],
    body: Annotated[str, typer.Argument(help=HELP.pr.reply_body)],
) -> None:
    """Post an in-thread reply to a PR review discussion thread."""
    from devops_cli.github.pr_threads import reply_pr_review_thread

    comment = reply_pr_review_thread(thread_id, body)
    print_success(f"In-thread reply posted successfully (Comment ID: [bold]{comment.id}[/bold])")


@threads_app.command("resolve")
def resolve_threads(
    thread_ids: Annotated[list[str], typer.Argument(help=HELP.pr.thread_ids)],
) -> None:
    """Programmatically mark one or more PR review discussion threads as resolved."""
    from devops_cli.github.pr_threads import resolve_pr_review_thread

    resolved_count = 0
    for tid in thread_ids:
        res = resolve_pr_review_thread(tid)
        if res.success:
            resolved_count += 1
            print_success(f"Thread [bold]{tid}[/bold] marked as resolved.")

    print_success(f"Successfully resolved {resolved_count}/{len(thread_ids)} review thread(s).")


@threads_app.command("unresolve")
def unresolve_thread(
    thread_id: Annotated[str, typer.Argument(help=HELP.pr.thread_id)],
) -> None:
    """Reopen a previously resolved PR review discussion thread."""
    from devops_cli.github.pr_threads import unresolve_pr_review_thread

    res = unresolve_pr_review_thread(thread_id)
    if res.success:
        print_success(f"Thread [bold]{thread_id}[/bold] reopened (unresolved).")
