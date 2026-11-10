"""`devops roadmap eval screen`: the verify screen against the reviewer alone (#4282, ADR 0019).

The command asks Jev the questions of the screen about each case of the golden set, reads what a
stored run of the reviewer alone (`devops roadmap eval verify`) found in each case, fits the cuts
on one fixed half of the cases and scores them on the other half, and repeats with the halves
swapped. It calls no reviewer. With `--from` it reads the rows of an earlier report and makes no
request. With `--dry-run` it makes no request. With `--write-cuts` it fits the cuts on all the
cases and writes the data file of the screen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.core.repo import resolve_store_path
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_info, write_stdout

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_screen_eval import ScreenRow

_STORE = "roadmap_eval/screen"


def _run(
    cases_dir: Path | None,
    reviewer: list[Path],
    from_report: Path | None,
    reviewer_usd: float | None,
    *,
    write_cuts: bool,
    dry_run: bool,
    as_json: bool,
) -> None:
    from devops_cli.config.constants import CONST_AI_JEV_MODEL
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.intake.intake_model import gateway_address
    from devops_cli.roadmap.stage.stage_eval_cases import cases_root, load_cases
    from devops_cli.roadmap.stage.stage_screen_eval import (
        read_split,
        render_screen,
        rows_from_report,
        screen_json,
        screen_rows,
        two_way,
    )

    settings = load_settings()
    gateway = gateway_address(settings.ai)
    cases = load_cases(cases_dir)
    if dry_run and from_report is None:
        texts = MESSAGES.roadmap
        render_request_plan(
            texts.screen_eval_dry_run.format(gateway=gateway, cases=len(cases)),
            [
                PlannedRequest(
                    method="POST",
                    target=f"{gateway}/systemone",
                    stdin=texts.screen_eval_dry_run_case.format(name=case.name),
                    repeat=texts.screen_eval_dry_run_repeat,
                )
                for case in cases
            ],
            [],
        )
        return
    rows: list[ScreenRow] = (
        rows_from_report(from_report)
        if from_report is not None
        else screen_rows(cases, reviewer, settings=settings)
    )
    reports = two_way(rows, read_split(cases_root(cases_dir)))
    now = datetime.now(UTC)
    taken = now.isoformat(timespec="seconds")
    report = screen_json(rows, reports, taken=taken, jev_model=CONST_AI_JEV_MODEL)
    if from_report is None:
        target = resolve_store_path(f"{_STORE}/{now:%Y%m%dT%H%M%SZ}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")
        print_info(MESSAGES.roadmap.stage_eval_stored.format(path=target))
    write_stdout(report if as_json else render_screen(rows, reports, reviewer_usd=reviewer_usd))
    if write_cuts:
        from devops_cli.roadmap.stage.stage_jev_screen import CUTS_FILE
        from devops_cli.roadmap.stage.stage_screen_eval import fitted_cuts

        CUTS_FILE.write_text(
            fitted_cuts(rows, reports, jev_model=CONST_AI_JEV_MODEL, day=f"{now:%Y-%m-%d}"),
            encoding="utf-8",
        )
        print_info(MESSAGES.roadmap.screen_eval_cuts_written.format(path=CUTS_FILE))


@dry_run_class("request-plan")
def screen_cmd(
    reviewer: Annotated[
        list[Path] | None, typer.Option("--reviewer", help=HELP.roadmap.eval_screen_reviewer)
    ] = None,
    from_report: Annotated[
        Path | None, typer.Option("--from", help=HELP.roadmap.eval_screen_from)
    ] = None,
    reviewer_usd: Annotated[
        float | None,
        typer.Option("--reviewer-usd", min=0.0, help=HELP.roadmap.eval_screen_reviewer_usd),
    ] = None,
    write_cuts: Annotated[
        bool, typer.Option("--write-cuts", help=HELP.roadmap.eval_screen_write_cuts)
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help=HELP.roadmap.eval_stage_json)] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_stage_dry_run)
    ] = False,
    cases_dir: Annotated[
        Path | None, typer.Option("--cases", help=HELP.roadmap.eval_stage_cases)
    ] = None,
) -> None:
    """Score the verify screen against the reviewer alone on the golden set."""
    _run(
        cases_dir,
        list(reviewer or ()),
        from_report,
        reviewer_usd,
        write_cuts=write_cuts,
        dry_run=dry_run or is_dry_run(),
        as_json=as_json,
    )
