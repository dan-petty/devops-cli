"""GitHub Pull Request management and governance command group."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from http import HTTPStatus
from pathlib import PurePosixPath
from typing import Annotated, Any, NamedTuple, cast
from urllib.parse import quote, urlencode

import typer
from packaging.version import Version

from devops_cli.config.constants import (
    CONST_AGENT_TASK_FILE_RE,
    CONST_AGENT_TASKS_DIR,
    CONST_CHANGELOG_FILENAME,
    CONST_CHANGELOG_FRAGMENT_NAME_RE,
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_CI_WORKFLOW_FILE,
    CONST_GH_API_HTTP_STATUS_RE,
    CONST_GH_CLI,
    CONST_GH_COMPARE_COMMITS_PER_PAGE,
    CONST_GH_COMPARE_FILES_CAP,
    CONST_GH_RAW_CONTENT_ACCEPT,
    CONST_ISSUE_STATE_OPEN,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PR_API_STATE_MAP,
    CONST_PR_FILE_CHANGED_STATUSES,
    CONST_PR_FILE_MODIFIED_STATUS,
    CONST_PR_FILE_REMOVED_STATUS,
    CONST_PR_FILE_WRITTEN_STATUSES,
    CONST_RELEASE_BRANCH_PREFIX,
    CONST_RELEASE_BRANCH_RE,
    CONST_RELEASE_CUT_FILES,
    CONST_RELEASE_PROCESS_BRANCH_RE,
    CONST_RELEASE_PROCESS_CUT_KIND,
    CONST_RELEASE_PROCESS_OPEN_KIND,
    CONST_RELEASE_SHARED_FILES,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_PR_LIMIT,
    DEFAULT_PR_STATE,
    DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
    DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS,
)
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.defect_classifier import (
    PRHardeningAudit,
    audit_pr_hardening,
    classify_defect_pr,
)
from devops_cli.github.issue_closure import extract_linked_issues, extract_part_references
from devops_cli.github.pr_monitor import sort_prs_oldest_first
from devops_cli.github.rate_limiter import run_gh
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)
from devops_cli.release.changelog_fragments import find_changelog_section
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


def _failing_check_runs(owner: str, repo_name: str, head_sha: str) -> tuple[list[str], list[str]]:
    """Return the names of concluded-failing and still-running checks and statuses for a commit."""
    from devops_cli.github.check_verdict import CheckBucket, _fetch_checks_from_rest

    verdict = _fetch_checks_from_rest(owner, repo_name, head_sha, runner=run_gh)
    if verdict.unread_reason:
        raise RuntimeError(verdict.unread_reason)

    failing = [
        item.name
        for item in verdict.items
        if item.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD)
    ]
    pending = [item.name for item in verdict.items if item.bucket == CheckBucket.PENDING]
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


_PR_FILES_API = "the pull request files API"
_COMPARE_API = "the compare API"


def _changed_file(entry: Any, api: str) -> ChangedFile:
    """Read one changed-file entry `api` returned, raising on one without a filename and status.

    `pulls/{n}/files` and `compare/{base}...{head}` give each file the same shape.
    """
    if not isinstance(entry, dict):
        raise GitHubOperationError(f"{api} returned a non-object entry")
    filename, status = entry.get("filename"), entry.get("status")
    if not isinstance(filename, str) or not isinstance(status, str):
        raise GitHubOperationError(f"{api} returned an entry without a filename or status")
    previous = entry.get("previous_filename")
    return ChangedFile(filename, status, previous if isinstance(previous, str) else "")


def _changed_files(entries: Any, api: str) -> list[ChangedFile]:
    """Read the changed-file entries `api` returned, raising when they are not a list."""
    if not isinstance(entries, list):
        raise GitHubOperationError(f"{api} returned no list")
    return [_changed_file(entry, api) for entry in entries]


def _gh_json(res: Any, api: str) -> Any:
    """The JSON a `gh api` call to `api` printed, raising when the call or the JSON failed."""
    if res.returncode != 0:
        raise GitHubOperationError(_gh_failure(res))
    try:
        return json.loads(res.stdout or "null")
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"malformed JSON from {api}: {exc}") from exc


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
    return _changed_files(_gh_json(res, _PR_FILES_API), _PR_FILES_API)


def _read_pr_files(pr_num: int, owner: str, repo_name: str) -> _ChangedFilesRead:
    """Read the changed files once per readiness run, keeping a failure for the caller to judge."""
    try:
        return _ChangedFilesRead(_fetch_pr_files(pr_num, owner, repo_name))
    except GitHubOperationError as exc:
        return _ChangedFilesRead([], str(exc))


def _check_pr_perimeter_changes(changed: _ChangedFilesRead) -> None:
    """Warn when the PR changes a file a review.toml suppression of this repository covers."""
    from devops_cli.ai.review.path_classes import load_review_config
    from devops_cli.core.repo import find_repo_root
    from devops_cli.review.suppression import (
        covering_suppressions,
        format_covering_suppressions,
        load_review_suppressions,
    )

    if not changed.files:
        return
    config = load_review_config(repo_root=find_repo_root())
    covering = covering_suppressions(
        [entry.filename for entry in changed.files], load_review_suppressions(config)
    )
    if covering:
        print_warning(format_covering_suppressions(covering))


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


def _default_branch(pr_data: dict[str, Any]) -> str:
    """The default branch of the PR's base repository; empty when unknown."""
    base = pr_data.get("base") or {}
    return str((base.get("repo") or {}).get("default_branch") or "")


def _is_release_pr(pr_data: dict[str, Any]) -> bool:
    """Whether this is the release PR: `release/vX.Y.Z` into the default branch, not from a fork."""
    default_branch = _default_branch(pr_data)
    into_default = default_branch != "" and _branch_ref(pr_data, "base") == default_branch
    head_ref = _branch_ref(pr_data, "head")
    release_head = CONST_RELEASE_BRANCH_RE.fullmatch(head_ref) is not None
    return _same_repository(pr_data) and into_default and release_head


def _release_process_kind(pr_data: dict[str, Any]) -> str | None:
    """The kind of release-process PR this is, `cut` or `open`; None for any other PR.

    Its head is `chore/cut-vX.Y.Z` or `chore/open-vX.Y.Z`, optionally followed by `-<slug>`,
    from the same repository, and its base is `release/vX.Y.Z` of the same version.
    """
    process = CONST_RELEASE_PROCESS_BRANCH_RE.fullmatch(_branch_ref(pr_data, "head"))
    release = CONST_RELEASE_BRANCH_RE.fullmatch(_branch_ref(pr_data, "base"))
    if process is None or release is None or not _same_repository(pr_data):
        return None
    return process["kind"] if process["version"] == release["version"] else None


class _ReleaseProcessPR(NamedTuple):
    """A release-process PR and the files it changes, read."""

    pr_data: dict[str, Any]
    pr_num: int
    owner: str
    repo_name: str
    files: list[ChangedFile]


class _DefaultBranchChanges(NamedTuple):
    """The paths the default branch changed since its merge base with a PR's base, both paths
    of a rename included, or why they could not be read."""

    paths: frozenset[str]
    error: str = ""


def _paths(changed: ChangedFile) -> tuple[str, ...]:
    """The path a change leaves the file at and, for a rename, the path it had before."""
    return tuple(path for path in (changed.filename, changed.previous_filename) if path)


def _paths_outside(files: list[ChangedFile], allowed: Callable[[str, str], bool]) -> list[str]:
    """Every path these changes touch that `allowed` refuses for its status, in order, once."""
    refused = (
        path for changed in files for path in _paths(changed) if not allowed(path, changed.status)
    )
    return list(dict.fromkeys(refused))


def _named_paths(paths: list[str]) -> str:
    """The paths a blocker names, bounded, since GitHub supplies them."""
    return ", ".join(paths)[:CONST_MAX_ERROR_DETAIL_LENGTH]


def _is_changelog_fragment(path: str) -> bool:
    """Whether the path is a changelog fragment, `changelog.d/<issue>.md`."""
    location = PurePosixPath(path)
    return (
        str(location.parent) == CONST_CHANGELOG_FRAGMENTS_DIR
        and CONST_CHANGELOG_FRAGMENT_NAME_RE.fullmatch(location.name) is not None
    )


def _cut_makes(path: str, status: str) -> bool:
    """Whether the cut commit makes this change: it modifies the cut's files, and removes the
    fragments it collects into CHANGELOG.md."""
    if status == CONST_PR_FILE_MODIFIED_STATUS:
        return path in CONST_RELEASE_CUT_FILES
    return status == CONST_PR_FILE_REMOVED_STATUS and _is_changelog_fragment(path)


def _is_cut_file(path: str, _status: str) -> bool:
    """Whether the path is one of the files the cut commit modifies, whatever the change."""
    return path in CONST_RELEASE_CUT_FILES


def _cut_hold(process: _ReleaseProcessPR) -> list[str] | None:
    """None for a cut that makes only the cut commit's changes, as `cut_release` writes them;
    otherwise one blocker naming the rest."""
    outside = _paths_outside(process.files, _cut_makes)
    if not outside:
        return None
    blocker = MESSAGES.pr.grounding_cut_changes_more.format(
        number=process.pr_num,
        cut_files=", ".join(CONST_RELEASE_CUT_FILES),
        fragments=f"{CONST_CHANGELOG_FRAGMENTS_DIR}/<issue>.md",
        head=_branch_ref(process.pr_data, "head"),
        outside=_named_paths(outside),
    )
    return [blocker]


def _compare_entries(payload: Any) -> Any:
    """The changed-file entries of a compare response; None when it holds none."""
    return payload.get("files") if isinstance(payload, dict) else None


def _fetch_default_branch_changes(process: _ReleaseProcessPR) -> list[ChangedFile]:
    """Read the files the default branch changed since its merge base with the PR's base, in one
    request, raising when GitHub can't say which.

    `compare/{base}...{default branch}` lists the files changed from the merge base to the
    default branch's tip.
    """
    base = process.pr_data.get("base") or {}
    sides = (str(base.get("sha") or base.get("ref") or ""), _default_branch(process.pr_data))
    spec = "...".join(quote(side, safe="/") for side in sides)
    query = urlencode({"per_page": CONST_GH_COMPARE_COMMITS_PER_PAGE})
    endpoint = f"repos/{process.owner}/{process.repo_name}/compare/{spec}?{query}"
    res = run_gh([CONST_GH_CLI, "api", endpoint], check=False, quiet=True)
    return _changed_files(_compare_entries(_gh_json(res, _COMPARE_API)), _COMPARE_API)


def _read_default_branch_changes(process: _ReleaseProcessPR) -> _DefaultBranchChanges:
    """What the default branch changed since its merge base with the PR's base, or why that
    was not read. A list as long as GitHub's cap may be cut short, so it shows nothing, and a
    payload that names no default branch can't name the compare's side, so none is sent."""
    if not _default_branch(process.pr_data):
        repo = f"{process.owner}/{process.repo_name}"
        return _DefaultBranchChanges(
            frozenset(), MESSAGES.pr.grounding_no_default_branch.format(repo=repo)
        )
    try:
        files = _fetch_default_branch_changes(process)
    except GitHubOperationError as exc:
        return _DefaultBranchChanges(frozenset(), str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])
    if len(files) >= CONST_GH_COMPARE_FILES_CAP:
        capped = MESSAGES.pr.grounding_merge_changes_capped.format(count=len(files))
        return _DefaultBranchChanges(frozenset(), capped)
    return _DefaultBranchChanges(frozenset(path for changed in files for path in _paths(changed)))


def _merge_hold(process: _ReleaseProcessPR) -> list[str] | None:
    """None for a merge of the default branch that changes only the cut's files and what the
    default branch changed since its merge base with the PR's base; otherwise one blocker
    naming the rest, or why the default branch's changes could not be read.

    Those are read only when the PR changes a file that is not one of the cut's.
    """
    outside = _paths_outside(process.files, _is_cut_file)
    if not outside:
        return None
    fields = {
        "number": process.pr_num,
        "default": _default_branch(process.pr_data) or MESSAGES.pr.grounding_unnamed_default_branch,
        "base": _branch_ref(process.pr_data, "base"),
        "head": _branch_ref(process.pr_data, "head"),
    }
    default_changes = _read_default_branch_changes(process)
    if default_changes.error:
        error = default_changes.error
        return [MESSAGES.pr.grounding_merge_changes_unread.format(**fields, error=error)]
    own = [path for path in outside if path not in default_changes.paths]
    if not own:
        return None
    return [MESSAGES.pr.grounding_merge_changes_more.format(**fields, outside=_named_paths(own))]


# What each kind of release-process PR may change to be exempt from grounding (#1344).
_RELEASE_PROCESS_HOLDS: dict[str, Callable[[_ReleaseProcessPR], list[str] | None]] = {
    CONST_RELEASE_PROCESS_CUT_KIND: _cut_hold,
    CONST_RELEASE_PROCESS_OPEN_KIND: _merge_hold,
}


def _release_process_hold(
    pr_data: dict[str, Any], pr_num: int, owner: str, repo_name: str, changed: _ChangedFilesRead
) -> list[str] | None:
    """The blockers that hold a PR to grounding before its checks, or None for a release-process
    PR that changes only what its kind may.

    Any other PR is held with none, and so is a release-process PR whose files were not read,
    since nothing shows what it changes; `_changed_files_were_read` names that.
    """
    kind = _release_process_kind(pr_data)
    if kind is None or changed.error:
        return []
    process = _ReleaseProcessPR(pr_data, pr_num, owner, repo_name, changed.files)
    return _RELEASE_PROCESS_HOLDS[kind](process)


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
    pr_data: dict[str, Any], pr_num: int, owner: str, repo_name: str, changed: _ChangedFilesRead
) -> tuple[bool, list[str]]:
    """Whether grounding applies to this PR, and the blockers that lead its checks.

    The release PR is exempt before any lookup, and a release-process PR that changes only what
    its kind may is exempt before the task-directory lookup; a merge of the default branch may
    first read one compare request. A release-process PR that changes more leads with a blocker
    naming the rest. A lookup that fails for any reason but a 404 can't rule grounding out, so
    the check still applies and the failure is a blocker of its own.
    """
    if _is_release_pr(pr_data):
        return False, []
    held = _release_process_hold(pr_data, pr_num, owner, repo_name, changed)
    if held is None:
        return False, []
    try:
        return _base_has_task_files(pr_data, owner, repo_name), held
    except GitHubOperationError as exc:
        blocker = MESSAGES.pr.grounding_tasks_dir_unread.format(
            number=pr_num, path=CONST_AGENT_TASKS_DIR, error=exc
        )
        return True, [*held, blocker]


class _GroundedItem(NamedTuple):
    """The Release and state of the one issue a PR is grounded on, or why it wasn't read."""

    release: str | None
    state: str | None = None
    error: str = ""


class _BaseChangelog(NamedTuple):
    """Whether `release/vX.Y.Z` holds the vX.Y.Z section of CHANGELOG.md the cut writes, or why
    that wasn't read."""

    has_section: bool
    error: str = ""


class _Grounding(NamedTuple):
    """What the grounding checks judge: the PR's base, the issues it closes, the issues it delivers
    part of, the files it changes, the Release and state of the one issue it is grounded on, read
    into a release branch or for a part, and, for a PR changing CHANGELOG.md, whether the cut wrote
    the release's section there."""

    pr_num: int
    repo: str
    base: str
    issues: list[int]
    parts: list[int]
    changed: _ChangedFilesRead
    item: _GroundedItem | None = None
    changelog: _BaseChangelog | None = None

    @property
    def issue(self) -> int | None:
        """The one issue the PR is grounded on: the one it closes, or the one it delivers part of
        when it closes none; None unless the body names exactly one of either."""
        named = [*self.issues, *self.parts]
        return named[0] if len(named) == 1 else None


def _issue_list(numbers: list[int]) -> str:
    """Issue numbers as a body names them: `#1, #2`."""
    return ", ".join(f"#{number}" for number in numbers)


def _names_one_issue(grounding: _Grounding) -> str | None:
    """The body closes exactly one issue, read as `devops roadmap close` will act on it, or,
    closing none, delivers part of exactly one with `Part of #<issue>`."""
    if grounding.issue is not None:
        return None
    texts, number = MESSAGES.pr, grounding.pr_num
    if grounding.issues and grounding.parts:
        return texts.grounding_closes_and_parts.format(
            number=number, issues=_issue_list(grounding.issues), parts=_issue_list(grounding.parts)
        )
    if grounding.parts:
        return texts.grounding_several_parts.format(
            number=number, count=len(grounding.parts), parts=_issue_list(grounding.parts)
        )
    if not grounding.issues:
        return texts.grounding_closes_no_issue.format(number=number, repo=grounding.repo)
    return texts.grounding_closes_several_issues.format(
        number=number, count=len(grounding.issues), issues=_issue_list(grounding.issues)
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
    """The PR adds, modifies or renames the task file of the one issue it is grounded on."""
    issue = grounding.issue
    if issue is None or grounding.changed.error:
        return None
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


def _base_changelog_was_read(grounding: _Grounding) -> str | None:
    """The base's CHANGELOG.md was read, so a change to it can be judged against the cut."""
    if grounding.changelog is None or not grounding.changelog.error:
        return None
    return MESSAGES.pr.grounding_changelog_unread.format(
        number=grounding.pr_num, base=grounding.base, error=grounding.changelog.error
    )


def _leaves_release_files_to_the_cut(grounding: _Grounding) -> str | None:
    """Into a release/* branch a PR leaves docs/ROADMAP.md to the cut, and CHANGELOG.md until
    the cut has written release/vX.Y.Z's section; a critical fix after the cut edits that
    section (#1450).

    Every such PR edited the same lines of both, so each merge made every other open PR
    conflict and run CI again (#933). Its changelog entry is a fragment of its own instead,
    except after the cut, where its edit of the section is the entry.
    """
    if not grounding.base.startswith(CONST_RELEASE_BRANCH_PREFIX) or grounding.changed.error:
        return None
    found = {
        path for changed in grounding.changed.files for path in _changes_a_release_file(changed)
    }
    changelog = grounding.changelog
    cut = changelog is not None and changelog.has_section
    if cut or (changelog is not None and changelog.error):
        # After the cut, or unread, which `_base_changelog_was_read` names.
        found.discard(CONST_CHANGELOG_FILENAME)
    if not found:
        return None
    texts = MESSAGES.pr
    issue = "<issue>" if grounding.issue is None else str(grounding.issue)
    blocker = texts.grounding_release_files_changed.format(
        number=grounding.pr_num,
        files=" and ".join(path for path in CONST_RELEASE_SHARED_FILES if path in found),
        base=grounding.base,
    )
    if cut:
        return blocker
    # Only the PR that closes an item adds its fragment, so a part PR's blocker names that PR.
    hint = (
        texts.grounding_release_files_part_fragment
        if grounding.parts
        else texts.grounding_release_files_fragment
    )
    return blocker + hint.format(
        fragment=f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{issue}.md", issue=issue
    )


def _item_was_read(grounding: _Grounding) -> str | None:
    """The issue the PR is grounded on was read, where its Release or state is judged."""
    if grounding.item is None or not grounding.item.error:
        return None
    return MESSAGES.pr.grounding_item_unread.format(
        number=grounding.pr_num, issue=grounding.issue, error=grounding.item.error
    )


def _delivers_an_item_of_its_release(grounding: _Grounding) -> str | None:
    """A PR into `release/vX.Y.Z` closes, or delivers part of, an item of release vX.Y.Z (#740).

    The release's scope is fixed when it starts, so work on an item of another release, or of
    the backlog, waits for that release. It judges the one issue the PR is grounded on, which
    `_names_one_issue` requires; a PR into the default branch is not judged.
    """
    branch = CONST_RELEASE_BRANCH_RE.fullmatch(grounding.base)
    if branch is None or grounding.item is None or grounding.item.error:
        return None
    version = Version(branch["version"])
    if in_release(grounding.item.release, version):
        return None
    texts = MESSAGES.pr
    placement = (
        texts.grounding_item_in_release.format(release=grounding.item.release)
        if grounding.item.release
        else texts.grounding_item_in_backlog
    )
    delivers = texts.grounding_item_part if grounding.parts else texts.grounding_item_closes
    return texts.grounding_item_not_in_release.format(
        number=grounding.pr_num,
        delivers=delivers.format(issue=grounding.issue),
        placement=placement,
        release=f"v{version}",
        base=grounding.base,
    )


def _delivers_part_of_an_open_item(grounding: _Grounding) -> str | None:
    """A part PR's item is open: each part lands before the PR that closes the item, its last."""
    item = grounding.item
    if not grounding.parts or item is None or item.error or item.state == CONST_ISSUE_STATE_OPEN:
        return None
    return MESSAGES.pr.grounding_part_of_closed_item.format(
        number=grounding.pr_num, issue=grounding.issue
    )


# Each check names what is missing, or returns None. A check that needs what an earlier one
# found missing returns None, so each failure is one blocker. A new rule is one more entry.
_GROUNDING_CHECKS: tuple[Callable[[_Grounding], str | None], ...] = (
    _names_one_issue,
    _changed_files_were_read,
    _changes_its_task_file,
    _base_changelog_was_read,
    _leaves_release_files_to_the_cut,
    _item_was_read,
    _delivers_an_item_of_its_release,
    _delivers_part_of_an_open_item,
)


def _grounded_item(reply: object) -> _GroundedItem:
    """The Release and state an `issues/{n}` reply names."""
    issue = reply if isinstance(reply, dict) else {}
    milestone, state = issue.get("milestone"), issue.get("state")
    title = milestone.get("title") if isinstance(milestone, dict) else None
    return _GroundedItem(
        title if isinstance(title, str) else None, state if isinstance(state, str) else None
    )


def _read_grounded_item(owner: str, repo_name: str, grounding: _Grounding) -> _GroundedItem | None:
    """The Release and state of the one issue a PR is grounded on, read into a release branch,
    whose item is judged by its Release, or for a part, whose item must be open; None otherwise."""
    into_release = CONST_RELEASE_BRANCH_RE.fullmatch(grounding.base) is not None
    if grounding.issue is None or not (into_release or grounding.parts):
        return None
    res = run_gh(
        [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/issues/{grounding.issue}"],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        return _GroundedItem(None, error=_gh_failure(res))
    try:
        return _grounded_item(json.loads(res.stdout or ""))
    except json.JSONDecodeError as exc:
        return _GroundedItem(None, error=f"malformed JSON: {exc}"[:CONST_MAX_ERROR_DETAIL_LENGTH])


def _edits_the_changelog(changed: ChangedFile) -> bool:
    """Whether this change edits CHANGELOG.md in place, as a critical fix after the cut does."""
    return (
        changed.filename == CONST_CHANGELOG_FILENAME
        and changed.status == CONST_PR_FILE_MODIFIED_STATUS
    )


def _read_base_changelog(
    owner: str, repo_name: str, base: str, changed: _ChangedFilesRead
) -> _BaseChangelog | None:
    """Whether `base`, a release branch, holds its version's CHANGELOG.md section, read only for
    a PR that edits CHANGELOG.md; None for any other PR, which leaves the file to the cut.

    It is read raw at the branch's tip: the cut may have landed after the PR's base commit, and
    the JSON contents API returns no content for a file above 1 MB.
    """
    branch = CONST_RELEASE_BRANCH_RE.fullmatch(base)
    if branch is None or not any(map(_edits_the_changelog, changed.files)):
        return None
    res = run_gh(
        [
            CONST_GH_CLI,
            "api",
            "-H",
            CONST_GH_RAW_CONTENT_ACCEPT,
            f"repos/{owner}/{repo_name}/contents/{CONST_CHANGELOG_FILENAME}?"
            + urlencode({"ref": base}),
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        return _BaseChangelog(False, _gh_failure(res))
    section = find_changelog_section(res.stdout or "", branch["version"])
    return _BaseChangelog(section is not None and bool(section.body.strip()))


def _grounding_blockers(
    pr_data: dict[str, Any], pr_num: int, owner: str, repo_name: str, changed: _ChangedFilesRead
) -> list[str]:
    """Require every item PR to close one issue, or deliver part of one open issue, change its
    task file and leave the files the cut writes alone (CHANGELOG.md until the cut has written
    its section), and a PR into `release/vX.Y.Z` to deliver an item of that release.

    The release PR delivers no single item and is exempt, and so is a release-process PR that
    changes only what its kind may. It applies where the base holds `docs/agent/tasks/`. Where
    it does not apply, an unread file list is a warning, since only the perimeter warning
    reads it.
    """
    applies, blockers = _grounding_scope(pr_data, pr_num, owner, repo_name, changed)
    if not applies:
        if changed.error:
            print_warning(
                MESSAGES.pr.changed_files_unread.format(number=pr_num, error=changed.error)
            )
        return []
    repo = f"{owner}/{repo_name}"
    body = str(pr_data.get("body") or "")
    base = _branch_ref(pr_data, "base")
    issues = [issue.number for issue in extract_linked_issues(body, repo)]
    named = _Grounding(pr_num, repo, base, issues, extract_part_references(body, repo), changed)
    grounding = named._replace(
        item=_read_grounded_item(owner, repo_name, named),
        changelog=_read_base_changelog(owner, repo_name, base, changed),
    )
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

    try:
        unresolved = list_pr_review_threads(owner, repo_name, pr_num, unresolved_only=True)
    except GitHubOperationError as exc:
        blockers.append(f"Could not retrieve review threads for PR #{pr_num}: {exc}")
    else:
        blockers.extend(
            _evaluate_threads_blockers(
                unresolved, pr_num, allow_replied_threads=allow_replied_threads
            )
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

    One of several PRs that deliver an item says Part of #<issue> instead of closing it. Grounding
    judges it on that issue, which is open, as it judges a PR on the issue it closes, and the PR
    that closes the item, its last, adds changelog.d/<issue>.md.

    Grounding applies to every PR but the release PR (release/vX.Y.Z into the default branch)
    and a release-process PR into release/vX.Y.Z that changes only what its kind may. A cut
    (chore/cut-vX.Y.Z) only modifies the files the cut commit writes, the version files,
    CHANGELOG.md and docs/ROADMAP.md, and removes changelog.d/<issue>.md fragments. A merge of
    the default branch (chore/open-vX.Y.Z) only changes those files and what the default
    branch changed since its merge base, read with one compare request. Either head may end
    in -<slug>. One that changes more is held, with a blocker naming the other files. Under
    grounding, a PR's body closes exactly one issue, and it adds, modifies or renames that
    issue's docs/agent/tasks/task-<issue>-*.md. Into a release/* branch it leaves
    docs/ROADMAP.md to the cut, and CHANGELOG.md until the cut has written release/vX.Y.Z's
    section, adding changelog.d/<issue>.md instead; a critical fix after the cut edits that
    section. Into release/vX.Y.Z, the issue it closes is in release vX.Y.Z. A base branch
    without docs/agent/tasks/ is exempt.
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


def _build_dispatch_ci_cmd(
    owner_repo: str,
    head_ref: str,
) -> list[str]:
    """Build GitHub CLI API invocation for dispatching the CI workflow."""
    endpoint = f"repos/{owner_repo}/actions/workflows/{CONST_CI_WORKFLOW_FILE}/dispatches"
    return [CONST_GH_CLI, "api", "-X", "POST", endpoint, "-f", f"ref={head_ref}"]


def _poll_head_sha_change(
    target_repo: str,
    number: int,
    pre_sha: str,
) -> tuple[dict[str, Any], bool]:
    """Poll PR details until head SHA changes or attempt bound is reached."""
    latest_pr: dict[str, Any] = {}
    for _ in range(DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS):
        time.sleep(DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS)
        latest_pr = _fetch_pr_details(number, target_repo)
        current_sha = latest_pr.get("head", {}).get("sha", "")
        if current_sha and current_sha != pre_sha:
            return latest_pr, True
    return latest_pr, False


def _dispatch_ci_for_head(
    target_repo: str,
    number: int,
    pr: dict[str, Any],
    pre_sha: str,
) -> tuple[bool, str]:
    """Poll PR head SHA and dispatch CI workflow once updated."""
    head_repo = pr.get("head", {}).get("repo")
    head_repo_name = head_repo.get("full_name") if isinstance(head_repo, dict) else None
    if not head_repo_name or head_repo_name != target_repo:
        fork_name = head_repo_name or "unknown fork"
        print_info(
            MESSAGES.pr.update_dispatch_ci_fork.format(
                number=number, fork=fork_name, workflow=CONST_CI_WORKFLOW_FILE
            )
        )
        return True, "fork"

    latest_pr, sha_changed = _poll_head_sha_change(target_repo, number, pre_sha)
    if not sha_changed:
        print_error(
            MESSAGES.pr.update_dispatch_ci_head_unchanged.format(
                number=number, workflow=CONST_CI_WORKFLOW_FILE
            ),
            prefix=False,
        )
        return False, "head unchanged"

    head_ref = str(latest_pr.get("head", {}).get("ref") or pr.get("head", {}).get("ref", ""))
    dispatch_cmd = _build_dispatch_ci_cmd(target_repo, head_ref)
    res = run_gh(dispatch_cmd, check=False, quiet=True)
    if res.returncode == 0:
        print_success(
            MESSAGES.pr.update_dispatch_ci_success.format(
                number=number, branch=head_ref, workflow=CONST_CI_WORKFLOW_FILE
            )
        )
        return True, "dispatched"

    error_msg = _parse_update_error(res.stderr or res.stdout)
    print_error(
        MESSAGES.pr.update_dispatch_ci_failed.format(
            number=number, workflow=CONST_CI_WORKFLOW_FILE, error=error_msg
        ),
        prefix=False,
    )
    return False, error_msg


def _plan_update_single_pr(
    number: int,
    target_repo: str,
    expected_head_sha: str | None = None,
    dispatch_ci: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for single PR update dry-run."""
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{number}"),
        ),
        PlannedRequest(
            method="PUT",
            target=f"repos/{target_repo}/pulls/{number}/update-branch",
            argv=tuple(_build_update_branch_cmd(target_repo, number, expected_head_sha)),
        ),
    ]
    if dispatch_ci:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"repos/{target_repo}/pulls/{number}",
                argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{number}"),
                repeat=f"up to {DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS}, {DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS:g}s apart",
            )
        )
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"repos/{target_repo}/actions/workflows/{CONST_CI_WORKFLOW_FILE}/dispatches",
                argv=tuple(_build_dispatch_ci_cmd(target_repo, "<branch>")),
                condition="the head changed and lives in this repository",
            )
        )
    return requests


def _plan_update_all_prs(
    target_repo: str | None,
    target_base: str | None,
    dispatch_ci: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for all PRs update dry-run."""
    list_argv = [
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
    if target_repo:
        list_argv.extend(["--repo", target_repo])
    if target_base:
        list_argv.extend(["--base", target_base])
    repo_slug = target_repo or ":owner/:repo"
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{repo_slug}/pulls",
            argv=tuple(list_argv),
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{repo_slug}/pulls/<number>",
            argv=(CONST_GH_CLI, "api", f"repos/{repo_slug}/pulls/<number>"),
            repeat="each open non-draft PR",
        ),
        PlannedRequest(
            method="PUT",
            target=f"repos/{repo_slug}/pulls/<number>/update-branch",
            argv=(
                CONST_GH_CLI,
                "api",
                "-X",
                "PUT",
                f"repos/{repo_slug}/pulls/<number>/update-branch",
            ),
            repeat="each open non-draft PR",
        ),
    ]
    if dispatch_ci:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"repos/{repo_slug}/pulls/<number>",
                argv=(CONST_GH_CLI, "api", f"repos/{repo_slug}/pulls/<number>"),
                repeat=f"each open non-draft PR; up to {DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS}, {DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS:g}s apart",
            )
        )
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"repos/{repo_slug}/actions/workflows/{CONST_CI_WORKFLOW_FILE}/dispatches",
                argv=tuple(_build_dispatch_ci_cmd(repo_slug, "<branch>")),
                condition="the head changed and lives in this repository",
                repeat="each open non-draft PR",
            )
        )
    return requests


def _update_single_pr(
    number: int,
    repo: str | None = None,
    expected_head_sha: str | None = None,
    dry_run: bool = False,
    dispatch_ci: bool = False,
) -> tuple[bool, str]:
    """Update a specific pull request branch from its base branch."""
    _require_gh_cli()
    from devops_cli.core.repo import get_repo_origin_name

    target_repo = repo or get_repo_origin_name()
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.", prefix=False)
        return False, "Target repository could not be determined."

    if dry_run or is_dry_run():
        plan = _plan_update_single_pr(
            number=number,
            target_repo=target_repo,
            expected_head_sha=expected_head_sha,
            dispatch_ci=dispatch_ci,
        )
        render_request_plan(
            MESSAGES.pr.update_dry_run_heading.format(number=number),
            plan,
            (MESSAGES.dry_run.placeholders_note,),
        )
        return True, "dry-run"

    pr = _fetch_pr_details(number, target_repo)
    base_ref = pr.get("base", {}).get("ref", "base")
    pre_sha = pr.get("head", {}).get("sha", "")

    cmd = _build_update_branch_cmd(target_repo, number, expected_head_sha)
    success, message = _execute_update_branch(cmd)
    if not success:
        print_error(
            MESSAGES.pr.update_branch_failed.format(number=number, error=message),
            prefix=False,
        )
        return False, message

    print_success(MESSAGES.pr.update_branch_success.format(number=number, base=base_ref))
    if not dispatch_ci:
        return True, message

    return _dispatch_ci_for_head(target_repo, number, pr, pre_sha)


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
    dispatch_ci: bool = False,
) -> list[str] | None:
    """Evaluate and update a single candidate PR, returning a summary table row."""
    num = pr.get("number")
    if not num:
        return None
    head = str(pr.get("headRefName", ""))
    b_ref = str(pr.get("baseRefName", ""))
    if bool(pr.get("isDraft", False)):
        return [f"#{num}", head, b_ref, "[dim]draft (skipped)[/dim]"]
    success, msg = _update_single_pr(
        int(num),
        repo=repo,
        dry_run=dry_run,
        dispatch_ci=dispatch_ci,
    )
    if not dispatch_ci:
        status_text = "[green]✓ updated[/green]" if success else "[red]✗ failed[/red]"
    elif success:
        status_text = (
            f"[green]✓ updated ({msg})[/green]"
            if msg in ("dispatched", "fork")
            else "[green]✓ updated[/green]"
        )
    else:
        status_text = (
            f"[yellow]✓ updated ({msg})[/yellow]"
            if msg == "head unchanged"
            else "[red]✗ failed[/red]"
        )
    return [f"#{num}", head, b_ref, status_text]


def _update_all_prs(
    base: str | None = None,
    repo: str | None = None,
    dry_run: bool = False,
    dispatch_ci: bool = False,
) -> None:
    """Update all open non-draft pull requests targeting base branch."""
    from devops_cli.core.repo import get_repo_origin_name

    target_repo = repo or get_repo_origin_name()
    target_base = base or _detect_active_release_branch()
    if dry_run or is_dry_run():
        plan = _plan_update_all_prs(
            target_repo=target_repo,
            target_base=target_base,
            dispatch_ci=dispatch_ci,
        )
        render_request_plan(
            MESSAGES.pr.update_all_dry_run_heading,
            plan,
            (MESSAGES.dry_run.placeholders_note,),
        )
        return

    prs = _fetch_open_prs(repo, target_base)
    if not prs:
        print_info(MESSAGES.pr.update_branch_no_prs)
        return

    prs = sort_prs_oldest_first(prs)

    rows: list[list[str]] = []
    for pr in prs:
        row = _process_candidate_pr_row(pr, repo=repo, dry_run=dry_run, dispatch_ci=dispatch_ci)
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
    dispatch_ci: Annotated[
        bool,
        typer.Option("--dispatch-ci", help=HELP.pr.update_dispatch_ci),
    ] = False,
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
        _update_all_prs(
            base=base,
            repo=repo,
            dry_run=dry_run,
            dispatch_ci=dispatch_ci,
        )
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
        dispatch_ci=dispatch_ci,
    )
    if not success and not (dry_run or is_dry_run()):
        raise typer.Exit(1)


def _fetch_pr_view_payload(number: int, repo: str | None = None) -> dict[str, Any] | None:
    """Fetch PR metadata and files via gh pr view."""
    cmd = [CONST_GH_CLI, "pr", "view", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    cmd.extend(["--json", "number,title,labels,files,state,mergedAt"])
    res = run_gh(cmd, check=False)
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        data = json.loads(res.stdout)
        return cast(dict[str, Any], data) if isinstance(data, dict) else None
    except json.JSONDecodeError, ValueError:
        return None


def _fetch_merged_prs_payload(limit: int, repo: str | None = None) -> list[dict[str, Any]]:
    """Fetch recent merged pull requests including file data."""
    cmd = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        "merged",
        "--limit",
        str(limit),
        "--json",
        "number,title,labels,files",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_gh(cmd, check=False)
    if res.returncode != 0 or not res.stdout.strip():
        return []
    try:
        data = json.loads(res.stdout)
        return cast(list[dict[str, Any]], data) if isinstance(data, list) else []
    except json.JSONDecodeError, ValueError:
        return []


def _ensure_pr_files(pr_item: dict[str, Any], repo: str | None = None) -> list[dict[str, Any]]:
    """Ensure PR payload includes files list, querying view if needed."""
    files = pr_item.get("files")
    if files is not None and isinstance(files, list):
        return cast(list[dict[str, Any]], files)
    number = int(pr_item.get("number", 0))
    if number > 0:
        viewed = _fetch_pr_view_payload(number, repo=repo)
        if viewed and isinstance(viewed.get("files"), list):
            return cast(list[dict[str, Any]], viewed["files"])
    return []


def _render_hardening_table(audits: list[PRHardeningAudit]) -> None:
    """Render audited defect pull requests as a formatted terminal table."""
    rows: list[list[str]] = []
    for a in audits:
        surfaces_desc = (
            ", ".join(f"{s} (+{a.surface_additions[s]})" for s in a.hardened_surfaces)
            if a.is_hardened
            else "—"
        )
        status_desc = "[green]Hardened[/green]" if a.is_hardened else "[red]Missing[/red]"
        rows.append(
            [
                f"#{a.number}",
                a.title,
                ", ".join(a.classification.reasons) or "defect",
                status_desc,
                surfaces_desc,
            ]
        )
    print_table(
        title=MESSAGES.pr.hardening_report_title,
        columns=[
            ("#", "right"),
            ("Title", "bold"),
            ("Defect Classification", "cyan"),
            "Status",
            ("Surfaces Added", "green"),
        ],
        rows=rows,
    )


def _render_hardening_json(audits: list[PRHardeningAudit]) -> None:
    """Emit JSON payload for audited defect pull requests."""
    payload = [
        {
            "pr_number": a.number,
            "title": a.title,
            "is_defect": a.classification.is_defect,
            "reasons": list(a.classification.reasons),
            "is_hardened": a.is_hardened,
            "empty_files": a.empty_file_list,
            "surfaces": a.surface_additions,
            "hardened_surfaces": list(a.hardened_surfaces),
        }
        for a in audits
    ]
    write_stdout(json.dumps(payload, indent=2) + "\n")


def _audit_single_pr(
    pr: int,
    repo: str | None,
    output_format: str,
    fail_on_missing: bool,
) -> None:
    """Audit hardening compliance for a single pull request by number."""
    payload = _fetch_pr_view_payload(pr, repo=repo)
    if payload is None:
        print_error(f"Failed to fetch pull request #{pr}")
        raise typer.Exit(1)

    files = payload.get("files")
    if not files:
        print_error(MESSAGES.pr.hardening_report_empty_files.format(number=pr))
        if fail_on_missing:
            raise typer.Exit(1)
        return

    classification = classify_defect_pr(payload.get("title", ""), payload.get("labels", []))
    if not classification.is_defect:
        print_info(MESSAGES.pr.hardening_report_pr_not_defect.format(number=pr))
        return

    audit = audit_pr_hardening(pr, payload.get("title", ""), payload.get("labels", []), files)
    if output_format.lower() == "json":
        _render_hardening_json([audit])
        if fail_on_missing and not audit.is_hardened:
            raise typer.Exit(1)
        return

    _render_hardening_table([audit])
    if audit.is_hardened:
        surfaces_str = ", ".join(
            f"{s} (+{audit.surface_additions[s]})" for s in audit.hardened_surfaces
        )
        print_success(
            MESSAGES.pr.hardening_report_single_passed.format(number=pr, surfaces=surfaces_str)
        )
    else:
        print_error(MESSAGES.pr.hardening_report_single_failed.format(number=pr))
        if fail_on_missing:
            raise typer.Exit(1)


def _audit_all_defect_prs(
    limit: int,
    repo: str | None,
    output_format: str,
    fail_on_missing: bool,
) -> None:
    """Audit hardening compliance for all merged defect pull requests."""
    raw_prs = _fetch_merged_prs_payload(limit=limit, repo=repo)
    audits: list[PRHardeningAudit] = []
    for item in raw_prs:
        classification = classify_defect_pr(item.get("title", ""), item.get("labels", []))
        if classification.is_defect:
            files = _ensure_pr_files(item, repo=repo)
            audit = audit_pr_hardening(
                item.get("number", 0), item.get("title", ""), item.get("labels", []), files
            )
            audits.append(audit)

    if not audits:
        print_info(MESSAGES.pr.hardening_report_no_defects)
        return

    if output_format.lower() == "json":
        _render_hardening_json(audits)
        missing_count = sum(1 for a in audits if not a.is_hardened)
        if fail_on_missing and missing_count > 0:
            raise typer.Exit(1)
        return

    _render_hardening_table(audits)
    total = len(audits)
    hardened = sum(1 for a in audits if a.is_hardened)
    missing = total - hardened
    if missing > 0:
        print_warning(
            MESSAGES.pr.hardening_report_failed.format(missing_count=missing, total_count=total)
        )
        if fail_on_missing:
            raise typer.Exit(1)
    else:
        print_success(MESSAGES.pr.hardening_report_passed.format(count=total))


@app.command("hardening-report", help=HELP.pr.hardening_report)
def hardening_report_cmd(
    pr: Annotated[int | None, typer.Option("--pr", help=HELP.pr.hardening_report_pr)] = None,
    fail_on_missing: Annotated[
        bool, typer.Option("--fail-on-missing", help=HELP.pr.hardening_report_fail_on_missing)
    ] = False,
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.pr.target_repo)] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-n", min=1, help="Maximum number of merged PRs to inspect")
    ] = 100,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format (table, json)")
    ] = "table",
) -> None:
    """Audit merged defect pull requests for guardrail additions to declared hardening surfaces."""
    if pr is not None:
        _audit_single_pr(
            pr, repo=repo, output_format=output_format, fail_on_missing=fail_on_missing
        )
    else:
        _audit_all_defect_prs(
            limit=limit, repo=repo, output_format=output_format, fail_on_missing=fail_on_missing
        )


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
        raise typer.Exit(1) from exc

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
        raise typer.Exit(1) from exc

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
