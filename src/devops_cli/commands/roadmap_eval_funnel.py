"""`devops roadmap eval funnel`: item cohort conversion and cost funnel (#5494).

Follows each item cohort by ISO week of its latest active `status/ready` label event through the
steps of path `G1` or `continue`, combining paced GitHub REST timeline reads with Loki result-line
metric instant queries (`RESULT_LINES`). With `--dry-run`, sends 0 requests and prints the planned
queries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_OUTPUT_FORMAT_JSON
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import write_stdout
from devops_cli.output.serialization import emit_serialized


def _print_plan(since: datetime, repo: str | None, url: str) -> None:
    from devops_cli.roadmap.job_funnel import (
        loki_window_for,
        plan_funnel_github_requests,
        plan_funnel_queries,
        resolve_funnel_repos,
    )

    repos = resolve_funnel_repos(repo)
    render_request_plan(
        MESSAGES.roadmap.funnel_dry_run_github,
        plan_funnel_github_requests(repos, since=since),
    )
    window = loki_window_for(since, datetime.now(UTC))
    repo_filter = repos[0] if len(repos) == 1 else None
    queries = plan_funnel_queries(repo_filter, window=window)
    endpoint = f"{url.strip().rstrip('/')}/loki/api/v1/query"
    render_request_plan(
        MESSAGES.roadmap.funnel_dry_run_loki.format(count=len(queries), url=url),
        [PlannedRequest(method="GET", target=f"{endpoint}?query={q.expr}") for q in queries],
    )


@dry_run_class("request-plan")
def funnel_cmd(
    since: Annotated[str, typer.Option("--since", help=HELP.roadmap.eval_funnel_since)],
    repo: Annotated[str | None, typer.Option("--repo", help=HELP.roadmap.eval_funnel_repo)] = None,
    loki_url: Annotated[
        str | None, typer.Option("--loki-url", help=HELP.roadmap.eval_funnel_loki_url)
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_funnel_dry_run)
    ] = False,
) -> None:
    """Report roadmap item cohorts by ISO week and path (`G1` vs `continue`), with step conversion,
    Wilson 95% bounds, durations, and Loki token/cost totals."""
    from devops_cli.k8s.logql import resolve_loki_url
    from devops_cli.roadmap.job_funnel import (
        funnel_report,
        parse_since,
        render_funnel_report,
        resolve_funnel_repos,
    )

    since_dt = parse_since(since)
    repos = resolve_funnel_repos(repo)
    url = resolve_loki_url(loki_url)
    if dry_run or is_dry_run():
        _print_plan(since_dt, repo, url)
        return
    report = funnel_report(repos, since=since_dt, loki_url=url)
    if json_output:
        emit_serialized(report.model_dump(mode="json"), CONST_OUTPUT_FORMAT_JSON)
        return
    write_stdout(render_funnel_report(report))
