"""`devops roadmap eval stage`: the golden set of the stage job (#3028).

The command runs the real stage code on each case of `tests/fixtures/roadmap_eval/stage/` with the
model of the `analysis` task, or with `--model`, and prints a score for each type of defect. It
stores the score as JSON under the data directory. `--replay` makes no model call: it runs the
recorded plans through the deterministic gates and reports the defects each gate catches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.repo import find_repo_root, resolve_store_path
from devops_cli.dry_run import dry_run_class, is_dry_run, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, write_stdout

_STORE = "roadmap_eval/stage"


def _replay(
    cases_dir: Path | None, names: tuple[str, ...], limit: int | None, *, as_json: bool
) -> None:
    from devops_cli.roadmap.stage_eval_cases import load_cases, select_cases
    from devops_cli.roadmap.stage_eval_gates import replay_all
    from devops_cli.roadmap.stage_eval_render import render_replay, replay_json

    report = replay_all(select_cases(load_cases(cases_dir), names, limit))
    write_stdout(replay_json(report) if as_json else render_replay(report))
    if report.failures:
        raise typer.Exit(1)


def _run(
    cases_dir: Path | None,
    names: tuple[str, ...],
    limit: int | None,
    *,
    model: str | None,
    source: Path | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    from devops_cli.ai.client import get_llm_client
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.intake_model import gateway_address
    from devops_cli.roadmap.stage_eval_cases import load_cases, select_cases
    from devops_cli.roadmap.stage_eval_render import (
        planned_calls,
        render_score,
        score_json,
    )
    from devops_cli.roadmap.stage_eval_run import Outcome, run_cases
    from devops_cli.roadmap.stage_eval_score import score_runs

    cases = select_cases(load_cases(cases_dir), names, limit)
    settings = load_settings()
    gateway = gateway_address(settings.ai)
    if dry_run:
        render_request_plan(
            MESSAGES.roadmap.stage_eval_dry_run.format(gateway=gateway, cases=len(cases)),
            planned_calls(cases, gateway),
        )
        return
    client = get_llm_client(task="analysis", settings=settings, model=model)
    name = model or settings.ai.for_task("analysis").model
    runs = run_cases(cases, client, source or find_repo_root())
    score = score_runs(name, cases, runs)
    now = datetime.now(UTC)
    report = score_json(score, gateway=gateway, taken=now.isoformat(timespec="seconds"))
    target = resolve_store_path(f"{_STORE}/{now:%Y%m%dT%H%M%SZ}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    write_stdout(report if as_json else render_score(score, gateway=gateway))
    print_info(MESSAGES.roadmap.stage_eval_stored.format(path=target))
    failed = sum(run.outcome is Outcome.FAILED for run in runs)
    if failed:
        print_error(MESSAGES.roadmap.stage_eval_failed.format(failed=failed))
        raise typer.Exit(1)


@dry_run_class("request-plan")
def eval_stage_cmd(
    case: Annotated[
        list[str] | None, typer.Option("--case", help=HELP.roadmap.eval_stage_case)
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", help=HELP.roadmap.eval_stage_model)
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.eval_stage_limit)
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help=HELP.roadmap.eval_stage_json)] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_stage_dry_run)
    ] = False,
    replay: Annotated[bool, typer.Option("--replay", help=HELP.roadmap.eval_stage_replay)] = False,
    cases_dir: Annotated[
        Path | None, typer.Option("--cases", help=HELP.roadmap.eval_stage_cases)
    ] = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.eval_stage_source)
    ] = None,
) -> None:
    """Score the stage job on the golden set: the live run, or the replay through the gates."""
    names = tuple(case or ())
    if replay:
        _replay(cases_dir, names, limit, as_json=as_json)
        return
    _run(
        cases_dir,
        names,
        limit,
        model=model,
        source=source,
        dry_run=dry_run or is_dry_run(),
        as_json=as_json,
    )
