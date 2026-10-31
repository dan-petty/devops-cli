"""GitHub Pull Request management and governance command group."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from devops_cli.config.constants import (
    CONST_CI_WORKFLOW_FILE,
    CONST_GH_CLI,
    CONST_PR_API_STATE_MAP,
    CONST_PR_UPDATE_AUTHOR,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
)
from devops_cli.config.defaults import (
    DEFAULT_PR_LIMIT,
    DEFAULT_PR_STATE,
    DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
    DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS,
)
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.defect_classifier import (
    PRHardeningAudit,
    audit_pr_hardening,
    classify_defect_pr,
)
from devops_cli.github.error_classifier import is_gh_rate_limited
from devops_cli.github.merge_readiness import (
    CHECK_FAILURE_KINDS,
    AdvisoryLevel,
    BlockerKind,
    MergeReadiness,
    ReadinessOptions,
    assess_merge_readiness,
)
from devops_cli.github.pr_monitor import (
    PRMonitorResult,
    fetch_pr_details,
    sort_prs_oldest_first,
)
from devops_cli.github.rate_limiter import run_gh
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)
from devops_cli.roadmap import pull_labels
from devops_cli.roadmap.commit_title import commit_scope
from devops_cli.roadmap.github_store import label_args, repository_file_args
from devops_cli.roadmap.pull_status import set_delivered_status
from devops_cli.roadmap.title_labels import requested_labels

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


def _checkout() -> Path:
    """The root of the repository that holds the working directory, which the command reads here
    and nowhere else (#2127)."""
    from devops_cli.core.repo import find_repo_root

    return find_repo_root(Path.cwd())


def _target_repo(repo: str | None) -> str | None:
    """The repository: `--repo`, or the origin of the repository that holds the working
    directory."""
    from devops_cli.core.repo import get_repo_origin_name

    return repo or get_repo_origin_name(_checkout())


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
    target = _target_repo(repo)
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


def _split_target_repo(repo: str | None) -> tuple[str, str]:
    """The owner and name of `repo`, or of the checkout's origin; empty when neither names one."""
    target = _target_repo(repo)
    if not target or "/" not in target:
        return "", ""
    owner, repo_name = target.split("/", 1)
    return owner, repo_name


def _shown_pr(number: int, repo: str | None = None) -> dict[str, Any]:
    """Pull request `number` as `fetch_pr_details` reads it, for the commands that show what they
    can without it (`pr view`, `pr checks`, `pr update`): empty when it cannot be read."""
    owner, repo_name = _split_target_repo(repo)
    if not owner:
        return {}
    try:
        return fetch_pr_details(owner, repo_name, number, runner=run_gh)
    except GitHubOperationError as exc:
        logger.debug("PR #%s could not be read: %s", number, exc)
        return {}


def _render_pr_view_fallback(number: int, repo: str | None = None) -> bool:
    """Render PR details via REST API when gh pr view fails or hits rate limits."""
    pr = _shown_pr(number, repo)
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
    pr = _shown_pr(number, repo)
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

    verdict = fetch_pr_check_verdicts(number, repo=repo, runner=run_gh, checkout=_checkout())
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

    verdict = fetch_pr_check_verdicts(number, repo=repo, runner=run_gh, checkout=_checkout())
    _render_check_verdict_table(number, verdict)
    if verdict.exit_code != 0:
        raise typer.Exit(verdict.exit_code)


# =============================================================================
# Command: devops pr monitor (alias: wait)
# =============================================================================


def _render_monitor_summary(status: Any) -> None:
    """Render structured checks summary table."""
    if not status.checks:
        return
    rows = [
        [c.name, c.workflow or "-", _format_bucket_badge(c.bucket), c.link] for c in status.checks
    ]
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


def _handle_monitor_exit(result: PRMonitorResult, pr_number: int) -> None:
    """Print every blocker the monitor found, with the hint for each kind, and exit with its
    code: 1 for a failed or unread check, 2 for any other blocker, 3 on the timeout."""
    status = result.status
    if result.exit_code == 3:
        print_error(result.message, safe=True)
        raise typer.Exit(3)
    for blocker in status.blockers:
        print_error(blocker, prefix=False, safe=True)
    if status.unresolved_threads:
        _render_unresolved_threads_summary(status.unresolved_threads)
        print_warning(
            "Remediate issues with test-first fixes, reply in-thread via:\n"
            '  devops pr threads reply <thread_id> "<reply>"\n'
            "and resolve via:\n"
            "  devops pr threads resolve <thread_id>"
        )
    if status.checks_failed:
        print_warning("Inspect failed job logs via: gh run view --log-failed <run_id>")
    elif status.is_draft:
        print_warning(
            f"PR #{pr_number} is still a draft. Mark it ready with 'devops pr ready {pr_number}'."
        )
    raise typer.Exit(result.exit_code)


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
        md_lines.append(f"| {c.name} | {c.workflow or '-'} | {c.bucket.value} | {c.link} |")
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

    return resolve_branch_pr_number(owner=owner, repo=repo_name)


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
    """Wait until the checks of a PR settle, then name every blocker of its merge.

    While a check runs or a Copilot review is active, it waits. Then it reports the blockers of
    the merge-readiness verdict and of its review gate (requested changes, Copilot's review, an
    approval of the head with --require-reviews). Exit 0: ready; 1: a check failed or could not
    be read; 2: another blocker; 3: the timeout passed first.
    """
    _require_gh_cli()
    from devops_cli.github.pr_monitor import monitor_pr

    target_repo = _target_repo(repo)
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
    target = _target_repo(repo)
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


def _print_created_pr_message(stdout: str, base: str) -> int | None:
    """Name the draft the REST API opened, by its URL, or by its base when the reply names none.
    Return its number, or None when the reply names none."""
    try:
        data = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    number = data.get("number")
    if url := data.get("html_url"):
        print_success(MESSAGES.pr.draft_created.format(url=url))
    else:
        print_success(MESSAGES.pr.draft_created_into.format(base=base))
    return number if isinstance(number, int) else None


def _report_create_failure(res: Any, target_base: str | None) -> None:
    """Explain why a pull request could not be created.

    `run_gh` captures the GitHub CLI's output, so without this a failure printed nothing: the
    command exited non-zero with no message, and a base branch that did not exist was not named.
    """
    from devops_cli.security.sanitizer import mask_secrets

    detail = mask_secrets((res.stderr or res.stdout or "").strip()[:512])
    target = target_base or MESSAGES.pr.create_default_base
    print_error(
        f"Could not create the pull request against base '{target}'."
        + (f"\n{detail}" if detail else ""),
        safe=True,
    )
    if detail and "must first push" in detail:
        print_info("Push the branch first: git push -u origin HEAD")


def _repository_default_branch(owner: str, repo_name: str) -> str:
    """The repository's default branch from `repos/{owner}/{repo}`; empty when it can't be read."""
    res = run_gh([CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}"], check=False, quiet=True)
    if res.returncode != 0:
        return ""
    try:
        data = json.loads(res.stdout or "null")
    except json.JSONDecodeError:
        return ""
    return str(data.get("default_branch") or "") if isinstance(data, dict) else ""


def _fallback_create_pr(
    title: str,
    body: str,
    base: str | None,
    repo: str | None = None,
) -> bool:
    """Open the draft through REST `POST /pulls` when gh pr create fails (e.g. GraphQL rate
    limits), into `base` or else the repository's default branch."""
    target = _target_repo(repo)
    if not target or "/" not in target:
        return False
    owner, repo_name = target.split("/", 1)
    head = _detect_current_branch()
    if not head:
        return False

    existing = _find_existing_pr(owner, repo_name, head, base or "")
    if existing:
        num = existing.get("number", "")
        url = existing.get("html_url") or existing.get("url", "")
        print_success(f"Pull request #{num} already exists: {url}")
        return True

    target_base = base or _repository_default_branch(owner, repo_name)
    if not target_base:
        return False
    cmd = [
        CONST_GH_CLI,
        "api",
        f"repos/{owner}/{repo_name}/pulls",
        "-f",
        f"title={title}",
        "-f",
        f"body={body}",
        "-f",
        f"base={target_base}",
        "-f",
        f"head={head}",
        "-F",
        "draft=true",
    ]
    res = run_gh(cmd, check=False)
    if res.returncode == 0:
        number = _print_created_pr_message(res.stdout, target_base)
        if number is not None:
            _finish_created_pr(repo, number, title, base)
        return True
    return False


def _status_recorded(repo: str | None, number: int, status: str, state: str) -> bool:
    """Set `status` on the item that pull request `number` closes. A failure prints an error that
    names the pull request, which is already `state`, so the caller knows only the Status is
    missing, and returns False."""
    target = _target_repo(repo)
    if not target or "/" not in target:
        return True
    try:
        set_delivered_status(target, number, status)
    except GitHubOperationError as exc:
        print_error(
            MESSAGES.pr.status_not_set.format(number=number, state=state, error=exc), safe=True
        )
        return False
    return True


def _record_status(repo: str | None, number: int, status: str, state: str) -> None:
    """Set `status` as `_status_recorded` does, and exit 1 when it could not."""
    if not _status_recorded(repo, number, status, state):
        raise typer.Exit(1)


def _labels_recorded(repo: str | None, number: int, title: str, base: str | None) -> bool:
    """Add the labels that `title` gives to pull request `number` (#2748), as declared in the
    labels file on `base`. A scope with no declared label gets a warning. A failure prints an
    error that names the pull request, which stays open, and the labels, and returns False."""
    target = _target_repo(repo)
    if not target or "/" not in target:
        return True
    try:
        given = pull_labels.read_title_labels(target, title, ref=base)
        if given.undeclared_scope:
            print_warning(
                MESSAGES.pr.labels_scope_undeclared.format(
                    scope=commit_scope(title),
                    path=CONST_ROADMAP_LABELS_PATH,
                    label=given.undeclared_scope,
                ),
                to_stderr=True,
            )
        pull_labels.add_pull_labels(target, number, given.labels)
    except GitHubOperationError as exc:
        print_error(
            MESSAGES.pr.labels_not_set.format(repo=target, number=number, error=exc), safe=True
        )
        return False
    return True


def _plan_title_labels(repo: str | None, title: str, base: str | None) -> None:
    """Print the requests that a real `devops pr create` would send to label the new pull request:
    the read of the labels file, then one label request for each label the title asks for. The
    number of the pull request is a placeholder. Nothing is read or sent."""
    target = _target_repo(repo)
    if not target or "/" not in target:
        return
    asked = [label for label in requested_labels(title) if label]
    if not asked:
        return
    plan = [
        PlannedRequest(
            method="GET",
            target=f"repos/{target}/contents/{CONST_ROADMAP_LABELS_PATH}",
            argv=(
                CONST_GH_CLI,
                *repository_file_args(target, CONST_ROADMAP_LABELS_PATH, ref=base),
            ),
            condition="the pull request opens",
        ),
        *(
            PlannedRequest(
                method="POST",
                target=f"repos/{target}/issues/<number>/labels",
                argv=(CONST_GH_CLI, *label_args(target, "<number>", label)),
                condition=MESSAGES.pr.labels_dry_run_condition,
            )
            for label in asked
        ),
    ]
    render_request_plan(
        MESSAGES.pr.labels_dry_run_heading, plan, (MESSAGES.dry_run.placeholders_note,)
    )


def _finish_created_pr(repo: str | None, number: int, title: str, base: str | None) -> None:
    """Set the Status of the item that the new pull request closes, and give the pull request the
    labels of its title. Each step runs when the other fails. The command exits 1 if either failed,
    and the pull request stays open."""
    status_set = _status_recorded(repo, number, CONST_ROADMAP_STATUS_IN_PROGRESS, "open")
    labels_set = _labels_recorded(repo, number, title, base)
    if not (status_set and labels_set):
        raise typer.Exit(1)


@app.command("create")
def create_pr(
    title: Annotated[str, typer.Option("--title", "-t", help=HELP.options.title)],
    body: Annotated[str, typer.Option("--body", "-b", help=HELP.options.body)] = "",
    base: Annotated[
        str | None,
        typer.Option("--base", "-B", help=HELP.pr.create_base),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
) -> None:
    """Open a draft pull request, into the default branch unless --base names another.

    Every pull request opens as a draft. devops pr ready is the only way to mark it ready for
    review. It sets the Status of the roadmap item the pull request closes to In Progress. It also
    adds the labels that the Conventional Commit title gives, as intake does: fix(ai) gives type/bug
    and scope/ai. A scope that .github/labels.yml does not declare gets no label and a warning.
    """
    _require_gh_cli()
    cmd = [CONST_GH_CLI, "pr", "create", "--draft", "--title", title, "--body", body]
    if base:
        cmd.extend(["--base", base])
    if repo:
        cmd.extend(["--repo", repo])

    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        if _fallback_create_pr(title, body, base, repo):
            return
        _report_create_failure(res, base)
        raise typer.Exit(res.returncode)
    if url := res.stdout.strip():
        print_success(MESSAGES.pr.draft_created.format(url=url))
        last = url.rstrip("/").rsplit("/", 1)[-1]
        if last.isdigit():
            _finish_created_pr(repo, int(last), title, base)
        return
    print_success(
        MESSAGES.pr.draft_created_into.format(base=base or MESSAGES.pr.create_default_base)
    )
    if is_dry_run():
        _plan_title_labels(repo, title, base)


# =============================================================================
# Command: devops pr ready
# =============================================================================


def _handle_pr_ready_failure(stderr_text: str, number: int) -> None:
    """Handle and explain failures when marking a PR ready; a rate limit is what the gh
    classifier calls one."""
    from devops_cli.security.sanitizer import mask_secrets

    clean_err = mask_secrets(stderr_text.strip()[:256])
    if is_gh_rate_limited(stderr_text):
        # gh's rate-limit messages end with a period of their own.
        print_error(
            f"Failed to mark PR #{number} ready: GitHub GraphQL rate limit exceeded. "
            f"Details: {clean_err.removesuffix('.')}. "
            "Note: GitHub REST API PATCH /pulls does NOT support converting drafts. "
            "Wait for the GraphQL rate limit window to reset or convert via the GitHub web UI.",
            safe=True,
        )
        return
    print_error(f"Failed to mark PR #{number} ready: {clean_err or 'Unknown error'}", safe=True)


def _ready_check_blockers(number: int, verdict: MergeReadiness) -> None:
    """Stop `pr ready` on the verdict's checks: exit 1 when one failed or could not be read, 8
    while one runs."""
    failed = [b for b in verdict.blocking if b.kind in CHECK_FAILURE_KINDS]
    pending = [b for b in verdict.blocking if b.kind is BlockerKind.CHECKS_PENDING]
    for blocker in failed or pending:
        print_error(f"Cannot mark PR #{number} as ready for review: {blocker.text}", safe=True)
    if failed or pending:
        print_info("Pass --force to override failing check verification.")
        raise typer.Exit(1 if failed else 8)


def _validate_pr_ready(number: int, owner: str, repo_name: str, pr_data: dict[str, Any]) -> None:
    """Hold `pr ready` to the merge-readiness verdict's checks, and warn of each other blocker.

    Ready for review says the work is done and its checks pass; the merge itself stays gated by
    `check-readiness`, the required checks and a person. The pull request is a draft until this
    command runs, so its draft state blocks nothing here.
    """
    verdict = assess_merge_readiness(
        pr_data, owner, repo_name, number, options=ReadinessOptions(allow_draft=True)
    )
    _ready_check_blockers(number, verdict)
    for blocker in verdict.blocking:
        print_warning(f"Still blocks the merge: {blocker.text}")


def _verify_pr_draft_transition(number: int, owner: str, repo_name: str) -> None:
    """Verify that the pull request transitioned out of draft state."""
    post_data = fetch_pr_details(owner, repo_name, number, runner=run_gh)
    if post_data.get("draft", True):
        print_error(MESSAGES.pr.pr_still_draft_error.format(number=number))
        raise typer.Exit(1)


def _read_pr_to_ready(number: int, owner: str, repo_name: str, force: bool) -> dict[str, Any]:
    """Read the pull request `pr ready` marks; a failed read stops it unless `force` is given,
    since a pull request it cannot read is no proof that its checks pass."""
    try:
        return fetch_pr_details(owner, repo_name, number, runner=run_gh)
    except GitHubOperationError:
        if not force:
            raise
        return {}


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
    """Mark a draft pull request as ready for review once its checks pass.

    It exits 1 when a check failed or could not be read and 8 while one runs. Every other
    blocker of the merge-readiness verdict prints as a warning. --force skips the checks. It
    sets the Status of the roadmap item the pull request closes to In Review.
    """
    _require_gh_cli()
    owner, repo_name = _split_target_repo(repo)
    if not owner:
        print_error("Target repository must be in OWNER/REPO format.")
        raise typer.Exit(1)
    pr_data = _read_pr_to_ready(number, owner, repo_name, force)
    if pr_data and not pr_data.get("draft", True):
        print_info(MESSAGES.pr.pr_already_ready.format(number=number))
        if monitor:
            monitor_pr_command(number=number, repo=repo)
        return

    if not force:
        _validate_pr_ready(number, owner, repo_name, pr_data)

    cmd = [CONST_GH_CLI, "pr", "ready", str(number)]
    if repo:
        cmd.extend(["--repo", repo])
    res = run_gh(cmd, check=False)
    if res.returncode != 0:
        _handle_pr_ready_failure(res.stderr, number)
        raise typer.Exit(1)

    _verify_pr_draft_transition(number, owner, repo_name)
    print_success(MESSAGES.pr.pr_marked_ready_success.format(number=number))
    _record_status(repo, number, CONST_ROADMAP_STATUS_IN_REVIEW, "ready")
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


def _resolve_readiness_target(repo: str | None, number: int | None) -> tuple[str, str, int]:
    """Resolve repository owner, name and target PR number."""
    from devops_cli.github.pr_monitor import resolve_branch_pr_number

    target_repo = _target_repo(repo)
    if not target_repo or "/" not in target_repo:
        print_error("Target repository must be in OWNER/REPO format.")
        raise typer.Exit(1)

    owner, repo_name = target_repo.split("/", 1)
    pr_num = number or resolve_branch_pr_number(owner=owner, repo=repo_name)
    return owner, repo_name, pr_num


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


def _render_merge_readiness(verdict: MergeReadiness, pr_num: int) -> None:
    """Print the verdict's advisories, the threads that block it, and then its blockers or the
    success line, exiting with code 1 if anything blocks."""
    for advisory in verdict.advisories:
        if advisory.level is AdvisoryLevel.INFO:
            print_info(advisory.text)
        else:
            print_warning(advisory.text)
    if verdict.threads_to_show:
        _render_threads_table(list(verdict.threads_to_show))
    _emit_readiness_status(list(verdict.blockers), pr_num)


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

    Grounding applies where the base holds openspec/changes/. The PR targets the default branch.
    It closes exactly one issue, an open issue of its own repository that holds a priority/*
    label: a roadmap item. GitHub closes that issue when the PR merges. The PR
    adds openspec/changes/archive/<date>-<issue>-<slug>/, which uv run devops openspec archive
    writes for that issue's change. Only that archive writes openspec/specs/ and
    openspec/changes/archive/.
    """
    owner, repo_name, pr_num = _resolve_readiness_target(repo, number)
    pr_data = fetch_pr_details(owner, repo_name, pr_num, runner=run_gh)

    if _check_pr_terminal_state(pr_data, pr_num):
        return

    if auto_resolve:
        _auto_resolve_replied_threads(owner, repo_name, pr_num)

    options = ReadinessOptions(
        allow_draft=allow_draft,
        allow_blocked_state=allow_blocked_state,
        allow_replied_threads=allow_replied_threads,
        allow_pending_checks=allow_pending_checks,
    )
    _render_merge_readiness(
        assess_merge_readiness(pr_data, owner, repo_name, pr_num, options=options), pr_num
    )


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
        latest_pr = _shown_pr(number, target_repo)
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


def _open_prs_argv(repo: str | None, base: str | None) -> list[str]:
    """The `gh pr list` arguments that list the open pull requests the current account wrote,
    into `base` when one is given."""
    argv = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        "open",
        "--author",
        CONST_PR_UPDATE_AUTHOR,
        "--limit",
        "100",
        "--json",
        "number,title,headRefName,baseRefName,isDraft",
    ]
    if repo:
        argv.extend(["--repo", repo])
    if base:
        argv.extend(["--base", base])
    return argv


def _plan_update_all_prs(
    target_repo: str | None,
    target_base: str | None,
    dispatch_ci: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for all PRs update dry-run."""
    list_argv = _open_prs_argv(target_repo, target_base)
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
    target_repo = _target_repo(repo)
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

    pr = _shown_pr(number, target_repo)
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
    """Fetch the open pull requests the current account wrote, into `base` when one is given,
    oldest first."""
    res = run_gh(_open_prs_argv(repo, base), check=False, quiet=True)
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
    """Update the open non-draft pull requests the current account wrote, into `base` when one
    is given.

    Only the account's own pull requests are updated, so a pull request that a bot or another
    person owns, such as the one release-please writes, is never merged into.
    """
    target_repo = _target_repo(repo)
    if dry_run or is_dry_run():
        plan = _plan_update_all_prs(
            target_repo=target_repo,
            target_base=base,
            dispatch_ci=dispatch_ci,
        )
        render_request_plan(
            MESSAGES.pr.update_all_dry_run_heading,
            plan,
            (MESSAGES.dry_run.placeholders_note,),
        )
        return

    prs = _fetch_open_prs(repo, base)
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
@dry_run_class("request-plan")
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
    from devops_cli.github.pr_threads import list_pr_review_threads

    target_repo = _target_repo(repo)
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
    from devops_cli.github.pr_threads import resolve_all_pr_review_threads

    target_repo = _target_repo(repo)
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
