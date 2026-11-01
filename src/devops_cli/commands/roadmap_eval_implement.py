"""`devops roadmap eval implement` (#3030): the score of the implement job on its fixtures.

The command is on demand. It calls the model through the gateway, so it is no row of `devops ci`.
`--check-only` is its offline mode: no model, no clone, no request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from devops_cli.config.constants import CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES
from devops_cli.core.repo import find_repo_root
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_muted, write_stdout

if TYPE_CHECKING:
    from devops_cli.roadmap.implement_eval import LoadedCase
    from devops_cli.roadmap.implement_eval_run import RunReport


def _refuse(message: str) -> NoReturn:
    print_error(message)
    raise typer.Exit(1)


def _refuse_options(
    *, check_only: bool, dry_run: bool, run_commands: bool, model: str | None
) -> None:
    """Refuse the options that cannot go together."""
    texts = MESSAGES.roadmap
    if check_only and dry_run:
        _refuse(texts.eval_implement_modes.format(first="--check-only", second="--dry-run"))
    if check_only and model is not None:
        _refuse(texts.eval_implement_modes.format(first="--check-only", second="--model"))
    if run_commands and not check_only:
        _refuse(texts.eval_implement_needs_check)


def _emit(report: RunReport, *, json_output: bool) -> None:
    """Print the report as JSON or as text."""
    from devops_cli.roadmap.implement_eval_run import render_report

    write_stdout(report.model_dump_json(indent=2) + "\n" if json_output else render_report(report))


def _check(cases: list[LoadedCase], source: Path, *, run_commands: bool, json_output: bool) -> None:
    """Evaluate the recorded results of the cases, and exit 1 when one differs from its record."""
    from devops_cli.roadmap.implement_eval_run import RunReport, check_recorded

    results = [
        r for case in cases for r in check_recorded(case, repo=source, commands=run_commands)
    ]
    report = RunReport(results=tuple(results))
    _emit(report, json_output=json_output)
    if report.differing:
        raise typer.Exit(1)


def _run(
    cases: list[LoadedCase], source: Path, model_name: str | None, *, json_output: bool
) -> None:
    """Run the step of each case with the model, report, and write the JSON report."""
    from devops_cli.roadmap.implement_eval_run import (
        RunReport,
        eval_model,
        report_directory,
        run_case,
        write_report,
    )

    model, window, name = eval_model(model_name)
    results = []
    for number, case in enumerate(cases, start=1):
        print_muted(
            MESSAGES.roadmap.eval_implement_running.format(
                name=case.name, number=number, total=len(cases)
            ),
            to_stderr=True,
        )
        results.append(run_case(case, repo=source, model=model, window=window))
    report = RunReport(model=name, results=tuple(results))
    _emit(report, json_output=json_output)
    saved = write_report(report, report_directory(), datetime.now(UTC))
    print_muted(MESSAGES.roadmap.eval_implement_saved.format(path=saved), to_stderr=True)


@dry_run_class("request-plan")
def implement_cmd(
    fixture: Annotated[
        list[str] | None, typer.Option("--fixture", "-F", help=HELP.roadmap.eval_implement_fixture)
    ] = None,
    fixtures: Annotated[
        Path | None, typer.Option("--fixtures", help=HELP.roadmap.eval_implement_fixtures)
    ] = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.eval_implement_source)
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", "-m", help=HELP.roadmap.eval_implement_model)
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help=HELP.roadmap.eval_implement_json)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_implement_dry_run)
    ] = False,
    check_only: Annotated[
        bool, typer.Option("--check-only", help=HELP.roadmap.eval_implement_check_only)
    ] = False,
    run_commands: Annotated[
        bool, typer.Option("--run-commands", help=HELP.roadmap.eval_implement_run_commands)
    ] = False,
) -> None:
    """Score the implement job on its fixtures, or check the recorded results of the fixtures."""
    from devops_cli.roadmap.implement_eval import choose_cases, load_cases

    dry = dry_run or is_dry_run()
    _refuse_options(check_only=check_only, dry_run=dry, run_commands=run_commands, model=model)
    root = find_repo_root()
    cases = choose_cases(
        load_cases(fixtures or root / CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES), tuple(fixture or ())
    )
    clone_from = source or root
    if dry:
        from devops_cli.config.settings import load_settings
        from devops_cli.roadmap.implement_eval_run import render_dry_run

        name = model or load_settings().ai.for_task("implement").model
        write_stdout(render_dry_run(cases, model=name))
    elif check_only:
        _check(cases, clone_from, run_commands=run_commands, json_output=json_output)
    else:
        _run(cases, clone_from, model, json_output=json_output)
