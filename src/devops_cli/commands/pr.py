"""GitHub Pull Request management and governance command group."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from http import HTTPStatus
from typing import Annotated, Any, NamedTuple, cast
from urllib.parse import urlencode

import typer
from packaging.version import Version

from devops_cli.config.constants import (
    CONST_AGENT_TASK_FILE_RE,
    CONST_AGENT_TASKS_DIR,
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_GH_API_HTTP_STATUS_RE,
    CONST_GH_CLI,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PR_API_STATE_MAP,
    CONST_PR_FILE_CHANGED_STATUSES,
    CONST_PR_FILE_WRITTEN_STATUSES,
    CONST_RELEASE_BRANCH_PREFIX,
    CONST_RELEASE_BRANCH_RE,
    CONST_RELEASE_PROCESS_BRANCH_RE,
    CONST_RELEASE_SHARED_FILES,
)
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE, DEFAULT_PR_LIMIT, DEFAULT_PR_STATE
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.issue_closure import extract_linked_issues
from devops_cli.github.pr_monitor import sort_prs_oldest_first
from devops_cli.github.rate_limiter import run_gh
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from devops_cli.roadmap.store import in_release

logger = logging.getLogger(__name__)

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
    res = run_gh(cmd, check=False)
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


def _format_pr_list_row(pr: dict[str, Any]) -> list[str]:
    """Format single PR dict (GraphQL or REST) into table row values."""
    number = str(pr.get("number", ""))
    title = str(pr.get("title", ""))
    head = str(pr.get("headRefName") or pr.get("head", {}).get("ref", ""))
    base = str(pr.get("baseRefName") or pr.get("base", {}).get("ref", ""))
    author_data = pr.get("author") or pr.get("user", {})
    if isinstance(author_data, dict):
        author = author_data.get("login", "")
    else:
        author = str(author_data)
    updated = str(pr.get("updatedAt") or pr.get("updated_at", ""))[:10]
    url = str(pr.get("url") or pr.get("html_url", ""))
    return [f"#{number}", title, head, base, author, updated, url]


def _render_pr_table(prs: list[dict[str, Any]], state: str) -> None:
    """Render list of PRs as a formatted table."""
    if not prs:
        print_warning(MESSAGES.pr.no_prs_found, prefix=False)
        return

    rows = [_format_pr_list_row(pr) for pr in prs]
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


def _filter_fallback_prs(raw_prs: Any, state: str, limit: int) -> list[dict[str, Any]] | None:
    """Filter and slice pull requests from REST API response."""
    if not isinstance(raw_prs, list):
        return None
    prs: list[dict[str, Any]] = [p for p in raw_prs if isinstance(p, dict)]
    if state == "merged":
        prs = [p for p in prs if p.get("merged_at") is not None]
    return prs[:limit]


def _render_pr_list_fallback(state: str, limit: int, repo: str | None = None) -> bool:
    """Fallback to REST API GET /pulls when gh pr list fails (e.g. GraphQL rate limits)."""
    from devops_cli.core.repo import get_repo_origin_name

    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        return False
    owner, repo_name = target.split("/", 1)
    api_state = CONST_PR_API_STATE_MAP.get(state, "open")
    fetch_limit = min(max(limit * 2, 50), 100) if state == "merged" else limit
    res = run_gh(
        [
            CONST_GH_CLI,
            "api",
            f"repos/{owner}/{repo_name}/pulls?state={api_state}&per_page={fetch_limit}",
        ],
        check=False,
    )
    if res.returncode != 0 or not res.stdout.strip():
        return False
    try:
        filtered = _filter_fallback_prs(json.loads(res.stdout), state, limit)
        if filtered is not None:
            _render_pr_table(filtered, state)
            return True
    except json.JSONDecodeError:
        pass
    return False


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

    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        if _render_pr_list_fallback(state, limit, repo):
            return
        print_error(f"Failed to list PRs: {res.stderr}", prefix=False)
        raise typer.Exit(res.returncode)

    try:
        prs = json.loads(res.stdout) if res.stdout.strip() else []
    except json.JSONDecodeError:
        prs = []

    _render_pr_table(prs, state)


# =============================================================================
# PR REST API Fallback Helpers
# =============================================================================


def _fetch_pr_details(number: int, repo: str | None = None) -> dict[str, Any]:
    """Fetch PR details via REST API (immune to GraphQL rate limit)."""
    from devops_cli.core.repo import get_repo_origin_name

    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        return {}
    owner, repo_name = target.split("/", 1)
    res = run_gh(
        [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/pulls/{number}"],
        check=False,
        quiet=True,
    )
    if res.returncode == 0 and res.stdout.strip():
        try:
            parsed = json.loads(res.stdout)
            if isinstance(parsed, dict):
                return cast(dict[str, Any], parsed)
        except json.JSONDecodeError:
            return {}
    return {}


def _render_pr_view_fallback(number: int, repo: str | None = None) -> bool:
    """Render PR details via REST API when gh pr view fails or hits rate limits."""
    pr = _fetch_pr_details(number, repo)
    if not pr:
        return False
    title = str(pr.get("title", ""))
    state = str(pr.get("state", "open")).upper()
    draft = " [yellow](Draft)[/yellow]" if pr.get("draft") else ""
    head = str(pr.get("head", {}).get("ref", ""))
    base = str(pr.get("base", {}).get("ref", ""))
    user_data = pr.get("user", {})
    author = user_data.get("login", "") if isinstance(user_data, dict) else str(user_data)
    url = str(pr.get("html_url", ""))
    body = str(pr.get("body") or "").strip()

    print_table(
        title=f"Pull Request #{number}: {title}",
        columns=["Property", "Value"],
        rows=[
            ["Status", f"{state}{draft}"],
            ["Author", author],
            ["Branch", f"{head} -> {base}"],
            ["URL", url],
        ],
    )
    if body:
        from devops_cli.output import write_stream
        from devops_cli.security.sanitizer import mask_secrets

        write_stream(f"\nDescription:\n{mask_secrets(body)}\n\n")
    return True


def _resolve_pr_head_sha(number: int, repo: str | None = None) -> str:
    """Retrieve the head commit SHA for a pull request."""
    pr = _fetch_pr_details(number, repo)
    if not pr:
        return ""
    head_data = pr.get("head", {})
    return head_data.get("sha", "") if isinstance(head_data, dict) else ""


def _format_bucket_badge(bucket: Any) -> str:
    """Format check bucket with color coding."""
    val = bucket.value if hasattr(bucket, "value") else str(bucket)
    if val == "pass":
        return "[green]✓ pass[/green]"
    if val == "skipping":
        return "[dim]– skipping[/dim]"
    if val == "pending":
        return "[yellow]● pending[/yellow]"
    if val == "cancel":
        return "[bold magenta]⊘ cancel[/bold magenta]"
    if val == "fail":
        return "[bold red]✗ fail[/bold red]"
    return "[bold red]? unread[/bold red]"


def _render_check_verdict_table(number: int, verdict: Any) -> None:
    """Render check verdict table using Rich print_table."""
    from devops_cli.security.sanitizer import mask_secrets

    if not verdict.items:
        if verdict.unread_reason:
            print_error(
                f"Failed to read checks for PR #{number}: {mask_secrets(verdict.unread_reason)}"
            )
        else:
            print_info(f"No check runs found for PR #{number}.")
        return

    rows = [
        [
            mask_secrets(item.name),
            _format_bucket_badge(item.bucket),
            mask_secrets(item.link),
        ]
        for item in verdict.items
    ]
    print_table(
        title=f"CI Quality Gate Checks (PR #{number})",
        columns=["Check", "Status", "URL"],
        rows=rows,
    )


def _render_pr_checks_fallback(number: int, repo: str | None = None) -> bool:
    """Render check runs via REST API when gh pr checks fails or hits rate limits."""
    from devops_cli.github.check_verdict import fetch_pr_check_verdicts

    verdict = fetch_pr_check_verdicts(number, repo=repo, runner=run_gh)
    _render_check_verdict_table(number, verdict)
    return True


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
    _require_gh_cli()
    from devops_cli.security.sanitizer import mask_secrets

    cmd = [CONST_GH_CLI, "pr", "view", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_gh(cmd, check=False)
    if res.stdout:
        typer.echo(mask_secrets(res.stdout.rstrip()))
    if res.returncode != 0:
        if _render_pr_view_fallback(number, repo):
            return
        raise typer.Exit(res.returncode)


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
    _require_gh_cli()
    from devops_cli.github.check_verdict import fetch_pr_check_verdicts

    verdict = fetch_pr_check_verdicts(number, repo=repo, runner=run_gh)
    _render_check_verdict_table(number, verdict)
    if verdict.exit_code != 0:
        raise typer.Exit(verdict.exit_code)


# =============================================================================
# Command: devops pr monitor (alias: wait)
# =============================================================================


def _format_check_badge(check: Any) -> str:
    """Format check status badge with color coding."""
    if check.is_success:
        return "[green]✓ Success[/green]"
    if check.is_failure:
        return f"[bold red]✗ {check.conclusion}[/bold red]"
    return f"[yellow]● {check.status}[/yellow]"


def _render_monitor_summary(status: Any) -> None:
    """Render structured checks summary table."""
    if not status.checks:
        return
    rows = [[c.name, c.workflow or "-", _format_check_badge(c), c.url] for c in status.checks]
    print_table(
        title=f"CI Quality Gate Checks (PR #{status.number})",
        columns=["Check", "Workflow", "Status", "URL"],
        rows=rows,
    )


def _render_unresolved_threads_summary(threads: list[Any]) -> None:
    """Render table of unresolved review discussion threads."""
    from devops_cli.security.sanitizer import mask_secrets

    rows = []
    for t in threads:
        author = t.comments[0].author if t.comments else "unknown"
        loc = f"{t.path}:{t.line}" if t.line else t.path
        body = mask_secrets(t.comments[0].body) if t.comments else ""
        first_comment = (body[:60] + "...") if len(body) > 60 else body
        first_comment = first_comment.replace("\n", " ")
        rows.append([t.id, loc, author, first_comment])
    print_table(
        title="Unresolved Review Discussion Threads",
        columns=["Thread ID", "Location", "Reviewer", "Comment"],
        rows=rows,
    )


def _handle_monitor_exit(result: Any, pr_number: int) -> None:
    """Handle non-zero exit states for devops pr monitor."""
    if result.exit_code == 1:
        print_error(
            ERRORS.pr.checks_failed.format(
                number=pr_number,
                failed_count=len(result.status.failing_checks),
            )
        )
        print_warning("Inspect failed job logs via: gh run view --log-failed <run_id>")
        raise typer.Exit(1)

    if result.exit_code == 2:
        if getattr(result.status, "is_draft", False):
            print_warning(result.message)
            raise typer.Exit(2)
        if result.status.unresolved_threads:
            print_error(
                ERRORS.pr.unresolved_threads.format(
                    number=pr_number,
                    count=len(result.status.unresolved_threads),
                )
            )
            _render_unresolved_threads_summary(result.status.unresolved_threads)
            print_warning(
                "Remediate issues with test-first fixes, reply in-thread via:\n"
                '  devops pr threads reply <thread_id> "<reply>"\n'
                "and resolve via:\n"
                "  devops pr threads resolve <thread_id>"
            )
            raise typer.Exit(2)
        print_error(result.message)
        raise typer.Exit(2)

    print_error(result.message)
    raise typer.Exit(3)


def _sanitize_threads_for_output(status_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply secret masking to review comment bodies in status dictionary."""
    from devops_cli.security.sanitizer import mask_secrets

    for thread in status_dict.get("unresolved_threads", []):
        for comment in thread.get("comments", []):
            if "body" in comment and isinstance(comment["body"], str):
                comment["body"] = mask_secrets(comment["body"])
    return status_dict


def _format_markdown_threads_section(threads: list[Any]) -> list[str]:
    """Format markdown section for unresolved threads."""
    from devops_cli.security.sanitizer import mask_secrets

    lines = [
        "",
        "## Unresolved Discussion Threads",
        "",
        "| Thread ID | Location | Reviewer | Comment |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for t in threads:
        auth = t.comments[0].author if t.comments else "unknown"
        loc = f"{t.path}:{t.line}" if t.line else t.path
        body = mask_secrets(t.comments[0].body) if t.comments else ""
        clean_b = body.replace("\n", " ")
        short_b = (clean_b[:60] + "...") if len(clean_b) > 60 else clean_b
        lines.append(f"| `{t.id}` | {loc} | {auth} | {short_b} |")
    return lines


def _format_markdown_monitor_summary(result: Any, pr_number: int) -> str:
    """Format markdown output representation for PR monitoring."""
    md_lines = [
        f"# PR #{pr_number} Monitoring Status",
        "",
        f"**State**: {'Ready for Merging' if result.success else 'Action Required'}",
        f"**Exit Code**: {result.exit_code}",
        f"**Message**: {result.message}",
        "",
        "## CI Quality Gate Checks",
        "",
        "| Check | Workflow | Status | URL |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for c in result.status.checks:
        badge = (
            "✓ Success"
            if c.is_success
            else (f"✗ {c.conclusion}" if c.is_failure else f"● {c.status}")
        )
        md_lines.append(f"| {c.name} | {c.workflow or '-'} | {badge} | {c.url} |")
    if result.status.unresolved_threads:
        md_lines.extend(_format_markdown_threads_section(result.status.unresolved_threads))
    return "\n".join(md_lines)


def _validate_monitor_args(
    output_format: str, interval: int, timeout: int, target_repo: str | None
) -> tuple[str, str]:
    """Validate arguments and parse target repo into owner and repo name."""
    valid_formats = {"table", "json", "yaml", "markdown"}
    if output_format not in valid_formats:
        print_error(
            f"Unsupported format: '{output_format}'. Supported formats: {', '.join(sorted(valid_formats))}."
        )
        raise typer.Exit(1)
    if interval < 1:
        print_error("Polling interval must be at least 1 second.")
        raise typer.Exit(1)
    if timeout < 1:
        print_error("Timeout must be at least 1 second.")
        raise typer.Exit(1)
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.")
        raise typer.Exit(1)
    parts = target_repo.split("/", 1)
    return parts[0], parts[1]


def _resolve_monitor_pr_number(number: int | None, owner: str, repo_name: str) -> int:
    """Resolve pull request number or discover from branch."""
    if number is not None:
        return number
    from devops_cli.github.pr_monitor import resolve_branch_pr_number

    try:
        return resolve_branch_pr_number(owner=owner, repo=repo_name)
    except GitHubOperationError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc


def _emit_structured_monitor_result(output_format: str, result: Any, pr_number: int) -> None:
    """Emit structured output for json, yaml, or markdown formats and exit if failing."""
    from devops_cli.output import print as print_out

    sanitized_payload = {
        "success": result.success,
        "exit_code": result.exit_code,
        "message": result.message,
        "status": _sanitize_threads_for_output(result.status.model_dump(mode="json")),
    }
    if output_format == "json":
        print_out(json.dumps(sanitized_payload, indent=2))
    elif output_format == "yaml":
        import yaml

        print_out(yaml.safe_dump(sanitized_payload, sort_keys=False))
    elif output_format == "markdown":
        print_out(_format_markdown_monitor_summary(result, pr_number))

    if result.exit_code != 0:
        raise typer.Exit(result.exit_code)


@app.command("monitor")
@app.command("wait")
def monitor_pr_command(
    number: Annotated[
        int | None,
        typer.Argument(help=HELP.pr.number),
    ] = None,
    interval: Annotated[
        int,
        typer.Option("--interval", "-i", min=1, help=HELP.pr.monitor_interval),
    ] = 60,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", min=1, help=HELP.pr.monitor_timeout),
    ] = 300,
    settle_timeout: Annotated[
        int,
        typer.Option("--settle-timeout", "-s", min=0, help=HELP.pr.settle_timeout),
    ] = 60,
    require_reviews: Annotated[
        bool,
        typer.Option("--require-reviews/--no-require-reviews", help=HELP.pr.require_reviews),
    ] = True,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = "table",
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Monitor PR checks, Copilot review sessions, and unresolved threads until ready."""
    _require_gh_cli()
    from devops_cli.core.repo import get_repo_origin_name
    from devops_cli.github.pr_monitor import monitor_pr

    target_repo = repo or get_repo_origin_name()
    owner, repo_name = _validate_monitor_args(output_format, interval, timeout, target_repo)
    pr_number = _resolve_monitor_pr_number(number, owner, repo_name)

    if output_format == "table":
        print_info(MESSAGES.pr.monitoring_pr.format(number=pr_number))

    last_reported = -1

    def _status_cb(st: Any, elapsed: int) -> None:
        nonlocal last_reported
        if st.completed_checks != last_reported:
            last_reported = st.completed_checks
            copilot_info = (
                f" | Copilot: {st.copilot_status.state}"
                if st.copilot_status.is_active or st.copilot_status.state != "idle"
                else ""
            )
            print_info(
                f"[{elapsed}s] Checks: {st.successful_checks}/{st.total_checks} passed "
                f"({st.completed_checks}/{st.total_checks} done){copilot_info}"
            )

    result = monitor_pr(
        owner=owner,
        repo=repo_name,
        pr_number=pr_number,
        timeout=timeout,
        interval=interval,
        settle_timeout=settle_timeout,
        require_reviews=require_reviews,
        status_callback=_status_cb if output_format == "table" else None,
    )

    if output_format in {"json", "yaml", "markdown"}:
        _emit_structured_monitor_result(output_format, result, pr_number)
        return

    _render_monitor_summary(result.status)

    if result.exit_code == 0:
        print_success(MESSAGES.pr.pr_ready_success.format(number=pr_number))
        return

    _handle_monitor_exit(result, pr_number)


# =============================================================================
# Command: devops pr edit
# =============================================================================


def _fallback_patch_pr(
    number: int,
    base: str | None = None,
    title: str | None = None,
    body: str | None = None,
    repo: str | None = None,
    milestone: str | None = None,
) -> bool:
    """Fallback to REST API PATCH when gh pr edit fails (e.g. rate limit)."""
    from devops_cli.core.repo import get_repo_origin_name

    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        return False
    owner, repo_name = target.split("/", 1)
    patch_cmd = [
        CONST_GH_CLI,
        "api",
        "--method",
        "PATCH",
        f"repos/{owner}/{repo_name}/pulls/{number}",
    ]
    if title is not None:
        patch_cmd.extend(["-f", f"title={title}"])
    if body is not None:
        patch_cmd.extend(["-f", f"body={body}"])
    if base is not None:
        patch_cmd.extend(["-f", f"base={base}"])
    pull_ok = True
    if len(patch_cmd) > 5:
        res = run_gh(patch_cmd, check=False)
        pull_ok = res.returncode == 0

    if milestone is not None:
        ms_cmd = [
            CONST_GH_CLI,
            "api",
            "--method",
            "PATCH",
            f"repos/{owner}/{repo_name}/issues/{number}",
            "-F",
            f"milestone={milestone}",
        ]
        res_ms = run_gh(ms_cmd, check=False)
        return pull_ok and res_ms.returncode == 0
    return pull_ok


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
    milestone: Annotated[
        str | None,
        typer.Option("--milestone", "-m", help=HELP.pr.edit_milestone),
    ] = None,
) -> None:
    """Edit pull request base branch, title, body, or milestone."""
    _require_gh_cli()
    if not any([title, body, base, milestone]):
        print_warning("No changes specified. Use --title, --body, --base, or --milestone.")
        return

    cmd = [CONST_GH_CLI, "pr", "edit", str(number)]
    if base:
        cmd.extend(["--base", base])
    if title:
        cmd.extend(["--title", title])
    if body:
        cmd.extend(["--body", body])
    if repo:
        cmd.extend(["--repo", repo])
    if milestone:
        cmd.extend(["--milestone", milestone])

    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        if _fallback_patch_pr(number, base, title, body, repo, milestone=milestone):
            print_success(f"Successfully updated PR #{number}")
            return
        raise typer.Exit(res.returncode)
    print_success(f"Successfully updated PR #{number}")


# =============================================================================
# Command: devops pr create
# =============================================================================


def _detect_current_branch() -> str | None:
    res = run_subprocess(["git", "branch", "--show-current"], check=False, quiet=True)
    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else None


def _find_existing_pr(owner: str, repo_name: str, head: str, base: str) -> dict[str, Any] | None:
    """Check if an open pull request already exists for the given head and base branches."""
    res = run_gh(
        [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/pulls?head={owner}:{head}&state=open"],
        check=False,
        quiet=True,
    )
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        items = json.loads(res.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list):
        return None

    for item in items:
        if isinstance(item, dict) and (not base or item.get("base", {}).get("ref") == base):
            return item
    return None


def _print_created_pr_message(stdout: str, base: str) -> None:
    """Print PR creation success message from REST API response."""
    try:
        data = json.loads(stdout) if stdout.strip() else {}
        url = data.get("html_url", "")
        num = data.get("number", "")
        print_success(f"Pull request #{num} created successfully: {url}")
    except json.JSONDecodeError:
        print_success(f"Pull request created successfully targeting base [bold]{base}[/bold]")


def _report_create_failure(res: Any, target_base: str) -> None:
    """Explain why a pull request could not be created.

    `run_gh` captures the GitHub CLI's output, so a failure here printed nothing at all --
    the command exited non-zero with no message beyond its own elapsed time. Three
    invocations in one session produced no pull request and no indication of why: the base
    branch had been deleted when its release merged, and nothing said so.
    """
    from devops_cli.security.sanitizer import mask_secrets

    detail = mask_secrets((res.stderr or res.stdout or "").strip()[:512])
    print_error(
        f"Could not create the pull request against base '{target_base}'."
        + (f"\n{detail}" if detail else ""),
        safe=True,
    )
    if detail and "must first push" in detail:
        print_info("Push the branch first: git push -u origin HEAD")


def _fallback_create_pr(
    title: str,
    body: str,
    base: str,
    draft: bool = False,
    repo: str | None = None,
) -> bool:
    """Fallback to REST API POST /pulls when gh pr create fails (e.g. GraphQL rate limits)."""
    from devops_cli.core.repo import get_repo_origin_name

    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        return False
    owner, repo_name = target.split("/", 1)
    head = _detect_current_branch()
    if not head:
        return False

    existing = _find_existing_pr(owner, repo_name, head, base)
    if existing:
        num = existing.get("number", "")
        url = existing.get("html_url") or existing.get("url", "")
        print_success(f"Pull request #{num} already exists: {url}")
        return True

    cmd = [
        CONST_GH_CLI,
        "api",
        f"repos/{owner}/{repo_name}/pulls",
        "-f",
        f"title={title}",
        "-f",
        f"body={body}",
        "-f",
        f"base={base}",
        "-f",
        f"head={head}",
    ]
    if draft:
        cmd.extend(["-F", "draft=true"])
    res = run_gh(cmd, check=False)
    if res.returncode == 0:
        _print_created_pr_message(res.stdout, base)
        return True
    return False


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

    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        if _fallback_create_pr(title, body, target_base, draft, repo):
            return
        _report_create_failure(res, target_base)
        raise typer.Exit(res.returncode)
    print_success(f"Pull request created successfully targeting base [bold]{target_base}[/bold]")


# =============================================================================
# Command: devops pr ready
# =============================================================================


def _handle_pr_ready_failure(stderr_text: str, number: int) -> None:
    """Handle and explain failures when marking a PR ready."""
    from devops_cli.security.sanitizer import mask_secrets

    clean_err = mask_secrets(stderr_text.strip()[:256])
    if "rate limit" in clean_err.lower():
        print_error(
            f"Failed to mark PR #{number} ready: GitHub GraphQL rate limit exceeded.\n"
            f"Details: {clean_err}\n"
            "Note: GitHub REST API PATCH /pulls does NOT support converting drafts. "
            "Wait for the GraphQL rate limit window to reset or convert via the GitHub web UI.",
            safe=True,
        )
        return
    print_error(f"Failed to mark PR #{number} ready: {clean_err or 'Unknown error'}", safe=True)


def _extract_pr_head_sha(pr_data: dict[str, Any] | None) -> str:
    """Extract git commit SHA from PR head data dictionary."""
    if not pr_data:
        return ""
    head = pr_data.get("head")
    return str(head.get("sha", "")) if isinstance(head, dict) else ""


def _emit_ready_check_pending(number: int, verdict: Any) -> None:
    """Emit pending check error and exit with code 8."""
    from devops_cli.github.check_verdict import CheckBucket

    pending = [item.name for item in verdict.items if item.bucket == CheckBucket.PENDING]
    print_error(
        f"Cannot mark PR #{number} as ready for review: {len(pending)} check(s) still pending: {', '.join(pending)}.",
        safe=True,
    )
    print_info("Pass --force to override failing check verification.")
    raise typer.Exit(8)


def _emit_ready_check_failures(number: int, verdict: Any) -> None:
    """Emit failing or unread check errors and exit with code 1."""
    from devops_cli.github.check_verdict import CheckBucket

    if verdict.fail_count > 0 or verdict.cancel_count > 0:
        failing = [
            f"{item.name} ({item.state or item.bucket.value})"
            for item in verdict.items
            if item.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL)
        ]
        print_error(
            f"Cannot mark PR #{number} as ready for review: {len(failing)} check(s) failed:",
            safe=True,
        )
        for item in failing:
            print_error(f"  ✗ {item}", prefix=False, safe=True)
        print_info("Pass --force to override failing check verification.")
        raise typer.Exit(1)

    reason = verdict.unread_reason or "unread check status"
    print_error(
        f"Cannot mark PR #{number} as ready for review: check verification failed closed: {reason}.",
        safe=True,
    )
    print_info("Pass --force to override failing check verification.")
    raise typer.Exit(1)


def _validate_pr_ready_checks(
    number: int, repo: str | None, pr_data: dict[str, Any] | None
) -> None:
    """Ensure PR has no failing commit check runs prior to marking ready."""
    from devops_cli.github.check_verdict import fetch_pr_check_verdicts

    sha = _extract_pr_head_sha(pr_data)
    if not sha:
        return
    try:
        verdict = fetch_pr_check_verdicts(number, repo=repo, head_sha=sha, runner=run_gh)
    except Exception as exc:
        print_error(
            f"Failed fetching PR #{number} check verdicts: {exc}. Pass --force to override.",
            safe=True,
        )
        raise typer.Exit(1) from exc

    if verdict.is_passing:
        return
    if verdict.exit_code == 8:
        _emit_ready_check_pending(number, verdict)
    _emit_ready_check_failures(number, verdict)


def _verify_pr_draft_transition(number: int, repo: str | None) -> None:
    """Verify that the pull request transitioned out of draft state."""
    post_data = _fetch_pr_details(number, repo)
    if not post_data or post_data.get("draft", True):
        print_error(MESSAGES.pr.pr_still_draft_error.format(number=number))
        raise typer.Exit(1)


@app.command("ready")
def ready_pr(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
    monitor: Annotated[
        bool,
        typer.Option("--monitor", "-m", help=HELP.pr.ready_monitor),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Bypass failing check verification and force ready status"
        ),
    ] = False,
) -> None:
    """Mark a draft pull request as ready for review."""
    _require_gh_cli()
    pr_data = _fetch_pr_details(number, repo)
    if pr_data and not pr_data.get("draft", True):
        print_info(MESSAGES.pr.pr_already_ready.format(number=number))
        if monitor:
            monitor_pr_command(number=number, repo=repo)
        return

    if not force:
        _validate_pr_ready_checks(number, repo, pr_data)

    cmd = [CONST_GH_CLI, "pr", "ready", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        _handle_pr_ready_failure(res.stderr, number)
        raise typer.Exit(1)

    _verify_pr_draft_transition(number, repo)
    print_success(MESSAGES.pr.pr_marked_ready_success.format(number=number))
    if monitor:
        monitor_pr_command(number=number, repo=repo)


# =============================================================================
# Command: devops pr diff
# =============================================================================


@app.command("diff")
def diff_pr(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
    color: Annotated[
        str,
        typer.Option("--color", help="Whether to colorize diff (always, never, auto)."),
    ] = "auto",
) -> None:
    """View diff of a pull request."""
    _require_gh_cli()
    cmd = [CONST_GH_CLI, "pr", "diff", str(number), "--color", color]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        from devops_cli.security.sanitizer import mask_secrets

        clean_err = mask_secrets(res.stderr.strip()[:256])
        print_error(f"Failed to fetch diff for PR #{number}: {clean_err}", safe=True)
        raise typer.Exit(res.returncode)
    if res.stdout:
        from devops_cli.output import write_stream
        from devops_cli.security.sanitizer import mask_secrets

        write_stream(mask_secrets(res.stdout))


# =============================================================================
# Command: devops pr close
# =============================================================================


@app.command("close")
def close_pr(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    comment: Annotated[
        str | None,
        typer.Option("--comment", "-c", help=HELP.pr.close_comment),
    ] = None,
    delete_branch: Annotated[
        bool,
        typer.Option("--delete-branch", "-d", help=HELP.pr.delete_branch),
    ] = False,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Close a pull request."""
    _require_gh_cli()
    cmd = [CONST_GH_CLI, "pr", "close", str(number)]
    if comment:
        cmd.extend(["--comment", comment])
    if delete_branch:
        cmd.append("--delete-branch")
    if repo:
        cmd.extend(["--repo", repo])
    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        from devops_cli.security.sanitizer import mask_secrets

        clean_err = mask_secrets(res.stderr.strip()[:256])
        print_error(f"Failed to close PR #{number}: {clean_err}", safe=True)
        raise typer.Exit(res.returncode)
    print_success(MESSAGES.pr.pr_closed_success.format(number=number))


# =============================================================================
# Command: devops pr check-readiness
# =============================================================================


def _render_threads_table(threads: list[Any]) -> None:
    """Render PR review threads as a rich table."""
    from devops_cli.security.sanitizer import mask_secrets

    rows: list[list[str]] = []
    for t in threads:
        status = "[green]Resolved[/green]" if t.is_resolved else "[bold yellow]Open[/bold yellow]"
        loc = f"{t.path}:{t.line}" if t.line else t.path
        author = t.comments[0].author if t.comments else ""
        raw_body = mask_secrets(t.comments[0].body) if (t.comments and t.comments[0].body) else ""
        first_comment = (raw_body[:50] + "...") if len(raw_body) > 50 else raw_body
        first_comment = first_comment.replace("\n", " ")
        rows.append([t.id, status, loc, author, first_comment])

    print_table(
        title="PR Review Discussion Threads",
        columns=["Thread ID", "Status", "Location", "Author", "First Comment"],
        rows=rows,
    )


def _check_mergeable_blocker(
    pr_data: dict[str, Any], pr_num: int, allow_blocked_state: bool = False
) -> str | None:
    """Evaluate whether PR mergeable state represents a merge blocker."""
    if pr_data.get("merged") is True:
        return None
    if pr_data.get("state", "").lower() == "closed":
        return f"PR #{pr_num} is closed without being merged."

    mergeable = pr_data.get("mergeable")
    mergeable_state = pr_data.get("mergeable_state", "")
    base_ref = pr_data.get("base", {}).get("ref", "")

    if mergeable is False or mergeable_state in ("dirty", "conflicting"):
        return f"PR #{pr_num} has merge conflicts with base branch '{base_ref}'."
    if mergeable is None or mergeable_state in ("unknown", ""):
        return (
            f"PR #{pr_num} mergeability is unresolved or still calculating on GitHub "
            f"(mergeable: {mergeable}, state: '{mergeable_state}')."
        )
    if mergeable_state == "blocked":
        if allow_blocked_state:
            print_warning(
                f"PR #{pr_num} merge state is currently 'blocked' by branch protection or pending checks."
            )
            return None
        return (
            f"PR #{pr_num} merge state is blocked by GitHub branch protection or checks "
            "(state: 'blocked')."
        )
    return None


def _evaluate_threads_blockers(
    unresolved: list[Any],
    pr_num: int,
    allow_replied_threads: bool,
) -> list[str]:
    """Evaluate unresolved review threads and return blocker error messages."""
    if not unresolved:
        return []

    if allow_replied_threads:
        from devops_cli.github.pr_threads import has_non_opener_reply

        unreplied = [t for t in unresolved if not has_non_opener_reply(t)]
        replied = [t for t in unresolved if has_non_opener_reply(t)]
        if replied:
            print_info(
                f"PR #{pr_num} has {len(replied)} review discussion thread(s) with replies awaiting reviewer resolution."
            )
        if unreplied:
            _render_threads_table(unreplied)
            return [f"PR #{pr_num} has {len(unreplied)} unreplied review discussion thread(s)."]
        return []

    _render_threads_table(unresolved)
    return [f"PR #{pr_num} has {len(unresolved)} unresolved review discussion thread(s)."]


def _classify_check_run(run: Any) -> tuple[str | None, str | None]:
    """Classify a single check run into (failing_name, pending_name)."""
    if not isinstance(run, dict):
        return None, None
    name = str(run.get("name") or "check")
    if run.get("status") != "completed":
        return None, name
    from devops_cli.github.check_verdict import CheckBucket, classify_check_item

    item = classify_check_item(
        name=name,
        conclusion=run.get("conclusion"),
        status=run.get("status"),
    )
    if item.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD):
        return item.name, None
    return None, None


def _extract_page_runs(page: Any) -> list[dict[str, Any]]:
    """Extract check runs from a single API payload page."""
    if not isinstance(page, dict):
        raise RuntimeError("GitHub check-runs API returned invalid page structure")
    check_runs = page.get("check_runs")
    if isinstance(check_runs, list):
        return check_runs
    if "name" in page:
        return [page]
    raise RuntimeError("GitHub check-runs API returned page without check_runs")


def _fetch_check_runs_payload(owner: str, repo_name: str, head_sha: str) -> list[dict[str, Any]]:
    """Fetch and decode all check-runs pages from GitHub API with pagination."""
    res = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "--paginate",
            "--slurp",
            f"repos/{owner}/{repo_name}/commits/{head_sha}/check-runs?per_page=100",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        err_msg = res.stderr.strip() or f"exit code {res.returncode}"
        raise RuntimeError(f"GitHub check-runs API error: {err_msg}")
    if not res.stdout.strip():
        raise RuntimeError("GitHub check-runs API returned empty response")
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Invalid JSON from check-runs API: {err}") from err

    if isinstance(data, list):
        return [run for page in data for run in _extract_page_runs(page)]
    if isinstance(data, dict):
        return _extract_page_runs(data)
    raise RuntimeError("GitHub check-runs API returned unexpected payload structure")


def _fetch_commit_statuses_payload(
    owner: str, repo_name: str, head_sha: str
) -> list[dict[str, Any]]:
    """Fetch commit status contexts from GitHub status API."""
    res = run_gh(
        [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/commits/{head_sha}/status"],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        err_msg = res.stderr.strip() or f"exit code {res.returncode}"
        raise RuntimeError(f"GitHub commit status API error: {err_msg}")
    if not res.stdout.strip():
        raise RuntimeError("GitHub commit status API returned empty response")
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Invalid JSON from commit status API: {err}") from err
    if not isinstance(data, dict):
        raise RuntimeError("GitHub commit status API returned non-object response")
    statuses = data.get("statuses")
    return statuses if isinstance(statuses, list) else []


def _failing_check_runs(owner: str, repo_name: str, head_sha: str) -> tuple[list[str], list[str]]:
    """Return the names of concluded-failing and still-running checks and statuses for a commit."""
    from devops_cli.github.check_verdict import CheckBucket, classify_check_item

    check_runs = _fetch_check_runs_payload(owner, repo_name, head_sha)
    failing: list[str] = []
    pending: list[str] = []
    for run in check_runs:
        fail, pend = _classify_check_run(run)
        if fail:
            failing.append(fail)
        elif pend:
            pending.append(pend)

    statuses = _fetch_commit_statuses_payload(owner, repo_name, head_sha)
    for st in statuses:
        if not isinstance(st, dict):
            continue
        item = classify_check_item(
            name=str(st.get("context") or "status"),
            state=st.get("state"),
        )
        if item.bucket == CheckBucket.PENDING:
            pending.append(item.name)
        elif item.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD):
            failing.append(item.name)

    return failing, pending


def _check_run_blockers(
    pr_data: dict[str, Any],
    pr_num: int,
    owner: str,
    repo_name: str,
    allow_pending_checks: bool,
) -> list[str]:
    """Report failing checks as blockers, and pending ones unless explicitly allowed."""
    head_sha = str(pr_data.get("head", {}).get("sha") or "")
    if not head_sha:
        return []

    try:
        failing, pending = _failing_check_runs(owner, repo_name, head_sha)
    except RuntimeError as err:
        return [f"PR #{pr_num} check verification failed closed: {err}"]

    blockers = (
        [f"PR #{pr_num} has {len(failing)} failing check(s): {', '.join(sorted(failing))}."]
        if failing
        else []
    )

    if pending:
        message = (
            f"PR #{pr_num} has {len(pending)} check(s) still running: {', '.join(sorted(pending))}."
        )
        if allow_pending_checks:
            print_warning(message)
        else:
            blockers.append(message)
    return blockers


class ChangedFile(NamedTuple):
    """A file a pull request changes, with GitHub's status for it (`added`, `removed`, ...).

    A renamed file also carries the path it had before.
    """

    filename: str
    status: str
    previous_filename: str = ""


class _ChangedFilesRead(NamedTuple):
    """The files a pull request changes, or why they could not be read."""

    files: list[ChangedFile]
    error: str = ""


def _gh_failure(res: Any) -> str:
    """Name a failed `gh` call by its own message, bounded for the blocker that repeats it."""
    return ((res.stderr or "").strip() or f"exit code {res.returncode}")[
        :CONST_MAX_ERROR_DETAIL_LENGTH
    ]


def _changed_file(entry: Any) -> ChangedFile:
    """Read one `pulls/{n}/files` entry, raising on one without a filename and status."""
    if not isinstance(entry, dict):
        raise GitHubOperationError("the pull request files API returned a non-object entry")
    filename, status = entry.get("filename"), entry.get("status")
    if not isinstance(filename, str) or not isinstance(status, str):
        raise GitHubOperationError(
            "the pull request files API returned an entry without a filename or status"
        )
    previous = entry.get("previous_filename")
    return ChangedFile(filename, status, previous if isinstance(previous, str) else "")


def _fetch_pr_files(pr_num: int, owner: str, repo_name: str) -> list[ChangedFile]:
    """Read every file a pull request changes, raising when GitHub can't say which.

    `run_gh` pages a `--paginate` request itself and stops at the first page shorter than the
    URL's `per_page`, assuming 100 when the URL sets none. This endpoint's default page is 30,
    so without `per_page=100` the read ended after 30 files.
    """
    res = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "--paginate",
            f"repos/{owner}/{repo_name}/pulls/{pr_num}/files?per_page={DEFAULT_GH_REST_PER_PAGE}",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        raise GitHubOperationError(_gh_failure(res))
    try:
        payload = json.loads(res.stdout or "null")
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(
            f"malformed JSON from the pull request files API: {exc}"
        ) from exc
    if not isinstance(payload, list):
        raise GitHubOperationError("the pull request files API returned no list")
    return [_changed_file(entry) for entry in payload]


def _read_pr_files(pr_num: int, owner: str, repo_name: str) -> _ChangedFilesRead:
    """Read the changed files once per readiness run, keeping a failure for the caller to judge."""
    try:
        return _ChangedFilesRead(_fetch_pr_files(pr_num, owner, repo_name))
    except GitHubOperationError as exc:
        return _ChangedFilesRead([], str(exc))


def _check_pr_perimeter_changes(changed: _ChangedFilesRead) -> None:
    """Warn if PR changed files intersect with the mitigated findings perimeter ledger."""
    try:
        from devops_cli.ai.review.mitigations import (
            find_perimeter_changes,
            format_perimeter_warning,
        )

        if not changed.files:
            return
        matches = find_perimeter_changes([entry.filename for entry in changed.files])
        if matches:
            print_warning(format_perimeter_warning(matches))
    except Exception as exc:
        logger.debug("Failed checking PR perimeter changes: %s", exc)


def _repo_full_name(side: dict[str, Any]) -> str:
    """The `owner/repo` one side of a pull request lives in, lower-cased; empty when unknown."""
    repo = side.get("repo")
    return str(repo.get("full_name") or "").lower() if isinstance(repo, dict) else ""


def _same_repository(pr_data: dict[str, Any]) -> bool:
    """Whether the PR's head lives in its base's repository rather than a fork."""
    head, base = pr_data.get("head") or {}, pr_data.get("base") or {}
    return _repo_full_name(head) != "" and _repo_full_name(head) == _repo_full_name(base)


def _branch_ref(pr_data: dict[str, Any], side: str) -> str:
    """The branch name on one side (`head` or `base`) of a pull request."""
    return str((pr_data.get(side) or {}).get("ref") or "")


def _is_release_pr(pr_data: dict[str, Any]) -> bool:
    """Whether this is the release PR: `release/vX.Y.Z` into the default branch, not from a fork."""
    base = pr_data.get("base") or {}
    default_branch = str((base.get("repo") or {}).get("default_branch") or "")
    into_default = default_branch != "" and base.get("ref") == default_branch
    release_head = CONST_RELEASE_BRANCH_RE.fullmatch(_branch_ref(pr_data, "head")) is not None
    return _same_repository(pr_data) and into_default and release_head


def _is_release_process_pr(pr_data: dict[str, Any]) -> bool:
    """Whether this PR opens or cuts a release rather than delivering an item.

    Its head is `chore/open-vX.Y.Z` or `chore/cut-vX.Y.Z`, optionally followed by `-<slug>`,
    from the same repository, and its base is `release/vX.Y.Z` of the same version.
    """
    process = CONST_RELEASE_PROCESS_BRANCH_RE.fullmatch(_branch_ref(pr_data, "head"))
    release = CONST_RELEASE_BRANCH_RE.fullmatch(_branch_ref(pr_data, "base"))
    if process is None or release is None:
        return False
    return process["version"] == release["version"] and _same_repository(pr_data)


def _base_has_task_files(pr_data: dict[str, Any], owner: str, repo_name: str) -> bool:
    """Whether the base commit holds the task directory, raising when GitHub can't say.

    A 404 means the repository keeps no task files. Only the answer matters, so `--silent`
    drops the listing.
    """
    base = pr_data.get("base") or {}
    query = urlencode({"ref": str(base.get("sha") or base.get("ref") or "")})
    res = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "--silent",
            f"repos/{owner}/{repo_name}/contents/{CONST_AGENT_TASKS_DIR}?{query}",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode == 0:
        return True
    status = CONST_GH_API_HTTP_STATUS_RE.search(res.stderr or "")
    if status is not None and int(status.group("status")) == HTTPStatus.NOT_FOUND:
        return False
    raise GitHubOperationError(_gh_failure(res))


def _grounding_scope(
    pr_data: dict[str, Any], pr_num: int, owner: str, repo_name: str
) -> tuple[bool, list[str]]:
    """Whether grounding applies to this PR, and the blocker a failed lookup leaves.

    A lookup that fails for any reason but a 404 can't rule grounding out, so the check still
    applies and the failure is a blocker of its own.
    """
    if _is_release_pr(pr_data) or _is_release_process_pr(pr_data):
        return False, []
    try:
        return _base_has_task_files(pr_data, owner, repo_name), []
    except GitHubOperationError as exc:
        blocker = MESSAGES.pr.grounding_tasks_dir_unread.format(
            number=pr_num, path=CONST_AGENT_TASKS_DIR, error=exc
        )
        return True, [blocker]


class _ClosedItem(NamedTuple):
    """The Release of the one issue a PR into `release/vX.Y.Z` closes, or why it wasn't read."""

    release: str | None
    error: str = ""


class _Grounding(NamedTuple):
    """What the grounding checks judge: the PR's base, the issues it closes, the files it changes,
    and, into a release branch, the Release of the one issue it closes."""

    pr_num: int
    repo: str
    base: str
    issues: list[int]
    changed: _ChangedFilesRead
    item: _ClosedItem | None = None


def _closes_one_issue(grounding: _Grounding) -> str | None:
    """The body closes exactly one issue, read as `gh issues close-merged` will act on it."""
    if len(grounding.issues) == 1:
        return None
    if not grounding.issues:
        return MESSAGES.pr.grounding_closes_no_issue.format(
            number=grounding.pr_num, repo=grounding.repo
        )
    return MESSAGES.pr.grounding_closes_several_issues.format(
        number=grounding.pr_num,
        count=len(grounding.issues),
        issues=", ".join(f"#{issue}" for issue in grounding.issues),
    )


def _changed_files_were_read(grounding: _Grounding) -> str | None:
    """The files the PR changes were read, so the task-file check has something to judge."""
    if not grounding.changed.error:
        return None
    return MESSAGES.pr.grounding_files_unread.format(
        number=grounding.pr_num, error=grounding.changed.error
    )


def _writes_task_file(changed: ChangedFile, issue: int) -> bool:
    """Whether this change leaves the issue's task file in the head."""
    match = CONST_AGENT_TASK_FILE_RE.fullmatch(changed.filename)
    return (
        match is not None
        and int(match.group("issue")) == issue
        and changed.status in CONST_PR_FILE_WRITTEN_STATUSES
    )


def _changes_its_task_file(grounding: _Grounding) -> str | None:
    """The PR adds, modifies or renames the task file of the one issue it closes."""
    if len(grounding.issues) != 1 or grounding.changed.error:
        return None
    issue = grounding.issues[0]
    if any(_writes_task_file(changed, issue) for changed in grounding.changed.files):
        return None
    return MESSAGES.pr.grounding_task_file_missing.format(
        number=grounding.pr_num, pattern=f"{CONST_AGENT_TASKS_DIR}/task-{issue}-*.md", issue=issue
    )


def _changes_a_release_file(changed: ChangedFile) -> list[str]:
    """The files the cut writes that this change adds, modifies, renames or removes."""
    if changed.status not in CONST_PR_FILE_CHANGED_STATUSES:
        return []
    paths = (changed.filename, changed.previous_filename)
    return [path for path in paths if path in CONST_RELEASE_SHARED_FILES]


def _leaves_release_files_to_the_cut(grounding: _Grounding) -> str | None:
    """A PR into a release branch leaves CHANGELOG.md and docs/ROADMAP.md to the cut.

    Every such PR edited the same lines of both, so each merge made every other open PR
    conflict and run CI again (#933). Its changelog entry is a fragment of its own instead.
    """
    if not grounding.base.startswith(CONST_RELEASE_BRANCH_PREFIX) or grounding.changed.error:
        return None
    found = {
        path for changed in grounding.changed.files for path in _changes_a_release_file(changed)
    }
    if not found:
        return None
    issue = str(grounding.issues[0]) if len(grounding.issues) == 1 else "<issue>"
    return MESSAGES.pr.grounding_release_files_changed.format(
        number=grounding.pr_num,
        files=" and ".join(path for path in CONST_RELEASE_SHARED_FILES if path in found),
        base=grounding.base,
        fragment=f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{issue}.md",
    )


def _closes_an_item_of_its_release(grounding: _Grounding) -> str | None:
    """A PR into `release/vX.Y.Z` closes an item of release vX.Y.Z (#740).

    The release's scope is fixed when it starts, so work on an item of another release, or of
    the backlog, waits for that release. It judges the one issue the body closes, which
    `_closes_one_issue` requires; a PR into the default branch is not judged.
    """
    branch = CONST_RELEASE_BRANCH_RE.fullmatch(grounding.base)
    if branch is None or grounding.item is None:
        return None
    issue = grounding.issues[0]
    if grounding.item.error:
        return MESSAGES.pr.grounding_item_unread.format(
            number=grounding.pr_num, issue=issue, error=grounding.item.error
        )
    version = Version(branch["version"])
    if in_release(grounding.item.release, version):
        return None
    placement = (
        MESSAGES.pr.grounding_item_in_release.format(release=grounding.item.release)
        if grounding.item.release
        else MESSAGES.pr.grounding_item_in_backlog
    )
    return MESSAGES.pr.grounding_item_not_in_release.format(
        number=grounding.pr_num,
        issue=issue,
        placement=placement,
        release=f"v{version}",
        base=grounding.base,
    )


# Each check names what is missing, or returns None. A check that needs what an earlier one
# found missing returns None, so each failure is one blocker. A new rule is one more entry.
_GROUNDING_CHECKS: tuple[Callable[[_Grounding], str | None], ...] = (
    _closes_one_issue,
    _changed_files_were_read,
    _changes_its_task_file,
    _leaves_release_files_to_the_cut,
    _closes_an_item_of_its_release,
)


def _read_closed_item(
    owner: str, repo_name: str, base: str, issues: list[int]
) -> _ClosedItem | None:
    """The Release of the one issue a PR into a release branch closes; None for any other PR."""
    if CONST_RELEASE_BRANCH_RE.fullmatch(base) is None or len(issues) != 1:
        return None
    res = run_gh(
        [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/issues/{issues[0]}"],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        return _ClosedItem(None, _gh_failure(res))
    try:
        issue = json.loads(res.stdout or "")
    except json.JSONDecodeError as exc:
        return _ClosedItem(None, f"malformed JSON: {exc}"[:CONST_MAX_ERROR_DETAIL_LENGTH])
    milestone = issue.get("milestone") if isinstance(issue, dict) else None
    title = milestone.get("title") if isinstance(milestone, dict) else None
    return _ClosedItem(title if isinstance(title, str) else None)


def _grounding_blockers(
    pr_data: dict[str, Any], pr_num: int, owner: str, repo_name: str, changed: _ChangedFilesRead
) -> list[str]:
    """Require every item PR to close one issue, change its task file and leave shared files
    alone, and a PR into `release/vX.Y.Z` to close an item of that release.

    The release PR and release-process PRs deliver no single item and are exempt. It applies
    where the base holds `docs/agent/tasks/`. Where it does not apply, an unread file list is a
    warning, since only the perimeter warning reads it.
    """
    applies, blockers = _grounding_scope(pr_data, pr_num, owner, repo_name)
    if not applies:
        if changed.error:
            print_warning(
                MESSAGES.pr.changed_files_unread.format(number=pr_num, error=changed.error)
            )
        return []
    repo = f"{owner}/{repo_name}"
    linked = extract_linked_issues(str(pr_data.get("body") or ""), repo)
    base = _branch_ref(pr_data, "base")
    issues = [issue.number for issue in linked]
    item = _read_closed_item(owner, repo_name, base, issues)
    grounding = _Grounding(pr_num, repo, base, issues, changed, item)
    return blockers + [found for check in _GROUNDING_CHECKS if (found := check(grounding))]


def _evaluate_pr_blockers(
    pr_data: dict[str, Any],
    pr_num: int,
    owner: str,
    repo_name: str,
    allow_draft: bool = False,
    allow_blocked_state: bool = False,
    allow_replied_threads: bool = False,
    allow_pending_checks: bool = False,
) -> list[str]:
    """Inspect PR data, checks, discussion threads and grounding for merge blockers."""
    if pr_data.get("merged") is True:
        return []

    from devops_cli.github.pr_threads import list_pr_review_threads

    blockers: list[str] = []
    is_draft = pr_data.get("draft", False)

    merge_err = _check_mergeable_blocker(pr_data, pr_num, allow_blocked_state=allow_blocked_state)
    if merge_err:
        blockers.append(merge_err)

    # A draft cannot be merged, so it is a blocker rather than a warning. GitHub still
    # reports `mergeable_state: clean` for one, which is how a draft passed this check and
    # was reported ready.
    if is_draft and not allow_draft:
        blockers.append(f"PR #{pr_num} is in draft status; GitHub refuses to merge a draft.")
    elif is_draft:
        print_warning(f"PR #{pr_num} is in draft status and cannot be merged as-is.")

    blockers.extend(_check_run_blockers(pr_data, pr_num, owner, repo_name, allow_pending_checks))

    unresolved: list[Any] = []
    try:
        unresolved = list_pr_review_threads(owner, repo_name, pr_num, unresolved_only=True)
    except GitHubOperationError as exc:
        print_warning(f"Could not retrieve review threads for PR #{pr_num}: {exc}")

    blockers.extend(
        _evaluate_threads_blockers(unresolved, pr_num, allow_replied_threads=allow_replied_threads)
    )
    changed = _read_pr_files(pr_num, owner, repo_name)
    blockers.extend(_grounding_blockers(pr_data, pr_num, owner, repo_name, changed))
    _check_pr_perimeter_changes(changed)
    return blockers


def _resolve_readiness_target(repo: str | None, number: int | None) -> tuple[str, str, int, str]:
    """Resolve repository owner, name, target PR number, and target repo string."""
    from devops_cli.core.repo import get_repo_origin_name
    from devops_cli.github.pr_monitor import resolve_branch_pr_number

    target_repo = repo or get_repo_origin_name()
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.")
        raise typer.Exit(1)

    owner, repo_name = target_repo.split("/", 1)
    pr_num = number or resolve_branch_pr_number(owner=owner, repo=repo_name)
    return owner, repo_name, pr_num, target_repo


def _check_pr_terminal_state(pr_data: dict[str, Any], pr_num: int) -> bool:
    """Check if PR is already merged or closed unmerged.

    Returns True if PR is merged (caller should return success).
    Raises typer.Exit(1) if PR is closed without merging.
    Returns False if PR is open.
    """
    if pr_data.get("merged") is True:
        base_ref = pr_data.get("base", {}).get("ref", "")
        print_success(MESSAGES.pr.pr_already_merged.format(number=pr_num, base=base_ref))
        return True

    if pr_data.get("state", "").lower() == "closed":
        print_error(MESSAGES.pr.pr_closed_unmerged.format(number=pr_num))
        raise typer.Exit(1)

    return False


def _auto_resolve_replied_threads(owner: str, repo_name: str, pr_num: int) -> None:
    """Auto-resolve review discussion threads that already have replies."""
    from devops_cli.github.pr_threads import resolve_all_pr_review_threads

    resolved = resolve_all_pr_review_threads(owner, repo_name, pr_num, only_replied=True)
    count = sum(1 for r in resolved if r.success and r.is_resolved)
    if count > 0:
        print_success(f"Auto-resolved {count} replied review discussion thread(s).")


def _emit_readiness_status(blockers: list[str], pr_num: int) -> None:
    """Print readiness blockers or success message, exiting with code 1 if blocked."""
    if not blockers:
        print_success(f"PR #{pr_num} satisfies merge readiness: 0 conflicts, 0 unresolved threads.")
        return

    for blocker in blockers:
        print_error(blocker, prefix=False)
    raise typer.Exit(1)


@app.command("check-readiness")
def check_readiness(
    number: Annotated[
        int | None,
        typer.Argument(help="PR number to verify (defaults to current branch PR)"),
    ] = None,
    allow_draft: Annotated[
        bool,
        typer.Option("--allow-draft", help=HELP.pr.readiness_allow_draft),
    ] = False,
    allow_pending_checks: Annotated[
        bool,
        typer.Option("--allow-pending-checks", help=HELP.pr.readiness_allow_pending_checks),
    ] = False,
    allow_blocked_state: Annotated[
        bool,
        typer.Option(
            "--allow-blocked-state",
            help="Allow mergeable_state 'blocked' (e.g. when executing within CI while checks/approvals are pending)",
        ),
    ] = False,
    auto_resolve: Annotated[
        bool,
        typer.Option(
            "--auto-resolve",
            help=HELP.pr.check_readiness_auto_resolve,
        ),
    ] = False,
    allow_replied_threads: Annotated[
        bool,
        typer.Option(
            "--allow-replied-threads",
            help=HELP.pr.allow_replied_threads,
        ),
    ] = False,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.

    Grounding applies to every PR but the release PR (release/vX.Y.Z into the default branch)
    and release-process PRs (chore/open-vX.Y.Z or chore/cut-vX.Y.Z into release/vX.Y.Z): its
    body closes exactly one issue, and it adds, modifies or renames that issue's
    docs/agent/tasks/task-<issue>-*.md. Into a release/* branch it leaves CHANGELOG.md and
    docs/ROADMAP.md to the cut and adds changelog.d/<issue>.md instead. Into release/vX.Y.Z,
    the issue it closes is in release vX.Y.Z. A base branch without docs/agent/tasks/ is exempt.
    """
    owner, repo_name, pr_num, target_repo = _resolve_readiness_target(repo, number)
    pr_data = _fetch_pr_details(pr_num, target_repo)
    if not pr_data:
        print_error(f"Unable to retrieve details for PR #{pr_num}.")
        raise typer.Exit(1)

    if _check_pr_terminal_state(pr_data, pr_num):
        return

    if auto_resolve:
        _auto_resolve_replied_threads(owner, repo_name, pr_num)

    blockers = _evaluate_pr_blockers(
        pr_data,
        pr_num,
        owner,
        repo_name,
        allow_draft=allow_draft,
        allow_blocked_state=allow_blocked_state,
        allow_replied_threads=allow_replied_threads,
        allow_pending_checks=allow_pending_checks,
    )
    _emit_readiness_status(blockers, pr_num)


# =============================================================================
# Command: devops pr update
# =============================================================================


def _build_update_branch_cmd(
    owner_repo: str,
    number: int,
    expected_head_sha: str | None = None,
) -> list[str]:
    """Build GitHub CLI API invocation for updating a pull request branch."""
    endpoint = f"repos/{owner_repo}/pulls/{number}/update-branch"
    cmd = [CONST_GH_CLI, "api", "-X", "PUT", endpoint]
    if expected_head_sha:
        cmd.extend(["-f", f"expected_head_sha={expected_head_sha}"])
    return cmd


def _parse_update_error(raw_text: str) -> str:
    """Extract readable error message from gh api failure output."""
    clean = raw_text.strip()
    try:
        data = json.loads(clean)
        if isinstance(data, dict) and "message" in data:
            msg = str(data["message"])
            errors = data.get("errors")
            if isinstance(errors, list) and errors:
                return f"{msg}: {', '.join(str(e) for e in errors)}"
            return msg
    except json.JSONDecodeError:
        pass
    return clean or "Unknown API error"


def _execute_update_branch(cmd: list[str]) -> tuple[bool, str]:
    """Execute update-branch gh api command and return (success, message)."""
    res = run_gh(cmd, check=False, quiet=True)
    if res.returncode == 0:
        return True, "Branch update requested successfully."
    error_msg = _parse_update_error(res.stderr or res.stdout)
    return False, error_msg


def _update_single_pr(
    number: int,
    repo: str | None = None,
    expected_head_sha: str | None = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Update a specific pull request branch from its base branch."""
    _require_gh_cli()
    from devops_cli.core.repo import get_repo_origin_name

    target_repo = repo or get_repo_origin_name()
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.", prefix=False)
        return False, "Target repository could not be determined."

    pr = _fetch_pr_details(number, target_repo)
    head_ref = pr.get("head", {}).get("ref", f"PR #{number}")
    base_ref = pr.get("base", {}).get("ref", "base")

    if dry_run or is_dry_run():
        msg = MESSAGES.pr.update_branch_dry_run.format(
            number=number, branch=head_ref, base=base_ref
        )
        print_info(msg)
        return True, msg

    cmd = _build_update_branch_cmd(target_repo, number, expected_head_sha)
    success, message = _execute_update_branch(cmd)
    if success:
        print_success(MESSAGES.pr.update_branch_success.format(number=number, base=base_ref))
    else:
        print_error(
            MESSAGES.pr.update_branch_failed.format(number=number, error=message),
            prefix=False,
        )
    return success, message


def _fetch_open_prs(repo: str | None, base: str | None) -> list[dict[str, Any]]:
    """Fetch candidate open pull requests matching base branch in oldest-first order."""
    cmd = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,headRefName,baseRefName,isDraft",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    if base:
        cmd.extend(["--base", base])
    res = run_gh(cmd, check=False, quiet=True)
    if res.returncode != 0 or not res.stdout.strip():
        return []
    try:
        prs = json.loads(res.stdout)
        if not isinstance(prs, list):
            return []
        return sort_prs_oldest_first(prs)
    except json.JSONDecodeError:
        return []


def _process_candidate_pr_row(
    pr: dict[str, Any],
    repo: str | None,
    dry_run: bool,
) -> list[str] | None:
    """Evaluate and update a single candidate PR, returning a summary table row."""
    num = pr.get("number")
    if not num:
        return None
    head = str(pr.get("headRefName", ""))
    b_ref = str(pr.get("baseRefName", ""))
    if bool(pr.get("isDraft", False)):
        return [f"#{num}", head, b_ref, "[dim]draft (skipped)[/dim]"]
    success, _ = _update_single_pr(int(num), repo=repo, dry_run=dry_run)
    status_text = "[green]✓ updated[/green]" if success else "[red]✗ failed[/red]"
    return [f"#{num}", head, b_ref, status_text]


def _update_all_prs(
    base: str | None = None,
    repo: str | None = None,
    dry_run: bool = False,
) -> None:
    """Update all open non-draft pull requests targeting base branch."""
    target_base = base or _detect_active_release_branch()
    prs = _fetch_open_prs(repo, target_base)
    if not prs:
        print_info(MESSAGES.pr.update_branch_no_prs)
        return

    prs = sort_prs_oldest_first(prs)

    rows: list[list[str]] = []
    for pr in prs:
        row = _process_candidate_pr_row(pr, repo=repo, dry_run=dry_run)
        if row:
            rows.append(row)

    print_table(
        title=MESSAGES.pr.update_table_title,
        columns=["PR", "Head Branch", "Base Branch", "Status"],
        rows=rows,
    )


@app.command("update")
def update_pr(
    number: Annotated[
        int | None,
        typer.Argument(help=HELP.pr.update_number),
    ] = None,
    all_prs: Annotated[
        bool,
        typer.Option("--all", "-a", help=HELP.pr.update_all),
    ] = False,
    base: Annotated[
        str | None,
        typer.Option("--base", "-B", help=HELP.pr.update_base),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
    expected_head_sha: Annotated[
        str | None,
        typer.Option("--expected-head-sha", help=HELP.pr.update_expected_head_sha),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Update pull request branch with latest commits from its base branch."""
    _require_gh_cli()
    if dry_run:
        set_dry_run(True)

    if all_prs:
        _update_all_prs(base=base, repo=repo, dry_run=dry_run)
        return

    if number is None:
        print_error(
            "Please specify a PR number or use --all to update all open pull requests.",
            prefix=False,
        )
        raise typer.Exit(1)

    success, _ = _update_single_pr(
        number=number,
        repo=repo,
        expected_head_sha=expected_head_sha,
        dry_run=dry_run,
    )
    if not success and not (dry_run or is_dry_run()):
        raise typer.Exit(1)


# =============================================================================
# Command Group: devops pr threads
# =============================================================================

threads_app = new_typer(
    help=HELP.pr.threads_app,
    no_args_is_help=True,
)
app.add_typer(threads_app, name="threads")


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
    threads = []
    try:
        threads = list_pr_review_threads(owner, repo_name, number, unresolved_only=unresolved_only)
    except GitHubOperationError as exc:
        print_error(f"Failed to retrieve PR #{number} review threads: {exc}")
        raise typer.Exit(1)

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


def _validate_thread_reply_before_resolution(thread_id: str) -> None:
    """Ensure a review thread has a non-opener reply before allowing resolution."""
    from devops_cli.github.pr_threads import get_pr_review_thread, has_non_opener_reply

    try:
        thread = get_pr_review_thread(thread_id)
    except Exception as exc:
        print_error(f"Failed to fetch review thread {thread_id}: {exc}", prefix=False)
        raise typer.Exit(1)

    if not has_non_opener_reply(thread):
        print_error(
            f"Thread {thread_id} has no reply from someone other than the thread opener. "
            "Pass --without-reply to force resolution.",
            prefix=False,
        )
        raise typer.Exit(1)


@threads_app.command("resolve")
def resolve_threads(
    thread_ids: Annotated[list[str], typer.Argument(help=HELP.pr.thread_ids)],
    without_reply: Annotated[
        bool,
        typer.Option(
            "--without-reply",
            "-w",
            help=HELP.pr.threads_without_reply,
        ),
    ] = False,
) -> None:
    """Programmatically mark one or more PR review discussion threads as resolved."""
    from devops_cli.github.pr_threads import resolve_pr_review_thread

    if not without_reply:
        for tid in thread_ids:
            _validate_thread_reply_before_resolution(tid)

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


@threads_app.command("resolve-all")
def resolve_all_threads_cmd(
    number: Annotated[int, typer.Argument(help=HELP.pr.number)],
    only_replied: Annotated[
        bool,
        typer.Option("--only-replied/--all", help=HELP.pr.threads_only_replied),
    ] = True,
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.pr.target_repo)] = None,
) -> None:
    """Resolve all or replied review discussion threads for a pull request."""
    from devops_cli.core.repo import get_repo_origin_name
    from devops_cli.github.pr_threads import resolve_all_pr_review_threads

    target_repo = repo or get_repo_origin_name()
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.")
        raise typer.Exit(1)

    owner, repo_name = target_repo.split("/", 1)
    results = resolve_all_pr_review_threads(owner, repo_name, number, only_replied=only_replied)
    if not results:
        print_info(f"No unresolved candidate review threads found on PR #{number}.")
        return

    successful = [r for r in results if r.success and r.is_resolved]
    print_success(f"Resolved {len(successful)}/{len(results)} review thread(s) on PR #{number}.")
