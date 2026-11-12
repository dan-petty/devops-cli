"""`devops roadmap eval grades`: the job grade of each roadmap workflow from Loki (#5165).

The `eval` group scores a job on a golden set; this command scores each job on its live result
lines. The report lives in `roadmap/job_grade_report.py` and the grade table in
`roadmap/job_grade.py`. With `--dry-run` it sends no request and prints the queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import write_stdout
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.roadmap.job_grade import GradeWindow

if TYPE_CHECKING:
    from devops_cli.github.repo_ref import RepoRef


def _print_plan(window: GradeWindow, repo: RepoRef | None, url: str) -> None:
    from devops_cli.roadmap.job_grade_report import plan_grade_queries

    queries = plan_grade_queries(window, repo)
    endpoint = f"{url.strip().rstrip('/')}/loki/api/v1/query"
    render_request_plan(
        MESSAGES.roadmap.grades_dry_run.format(count=len(queries), url=url),
        [
            PlannedRequest(method="GET", target=f"{endpoint}?query={query.expr}")
            for query in queries
        ],
    )


@dry_run_class("request-plan")
def grades_cmd(
    repo: Annotated[str | None, typer.Option("--repo", help=HELP.roadmap.eval_grades_repo)] = None,
    window: Annotated[
        GradeWindow, typer.Option("--window", help=HELP.roadmap.eval_grades_window)
    ] = GradeWindow.D7,
    loki_url: Annotated[
        str | None, typer.Option("--loki-url", help=HELP.roadmap.eval_grades_loki_url)
    ] = None,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help=HELP.options.format_type)
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_grades_dry_run)
    ] = False,
) -> None:
    """Print the job grade of each roadmap workflow from its result lines in Loki."""
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.k8s.logql import resolve_loki_url
    from devops_cli.roadmap.job_grade_report import grade_report, render_grade_report

    fmt = resolve_format(output_format, json_output=json_output)
    ref = RepoRef(repo) if repo is not None else None
    url = resolve_loki_url(loki_url)
    if dry_run or is_dry_run():
        _print_plan(window, ref, url)
        return
    report = grade_report(window, ref, url)
    if fmt == CONST_OUTPUT_FORMAT_TABLE:
        write_stdout(render_grade_report(report))
        return
    emit_serialized(report.model_dump(mode="json"), fmt)
