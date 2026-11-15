"""`devops roadmap eval stage`: the golden set of the stage job (#3028).

The command runs the real stage code on each case of `tests/fixtures/roadmap_eval/stage/` with the
model of the `stage` task, or with `--model`, and prints a score for each type of defect. The
model plans with the read-only toolbox of the job; `--no-toolbox` plans with one call and no tool,
so two runs of one model compare (#3037). It
stores the score as JSON under the data directory. `--replay` makes no model call: it runs the
recorded plans through the deterministic gates and reports the defects each gate catches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import StageToolset
from devops_cli.core.repo import find_repo_root, resolve_store_path
from devops_cli.dry_run import dry_run_class, is_dry_run, render_request_plan
from devops_cli.exceptions import ValidationError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, write_stdout

_STORE = "roadmap_eval/stage"


def _constants_text(constants: tuple[tuple[str, int], ...]) -> str:
    """The constants of a case as `NAME = value`, or a note that its plan cites none."""
    if not constants:
        return MESSAGES.roadmap.stage_eval_record_none
    return ", ".join(f"{name} = {value}" for name, value in constants)


def _record(cases_dir: Path | None, names: tuple[str, ...], limit: int | None) -> None:
    """Write the constants that each selected case cites into its facts file, at its base commit."""
    from devops_cli.roadmap.stage.stage_eval_cases import cases_root, load_cases, select_cases
    from devops_cli.roadmap.stage.stage_eval_record import record_constants, write_constants

    cases = select_cases(load_cases(cases_dir), names, limit)
    root = cases_root(cases_dir)
    source = find_repo_root()
    no_commit = [case.name for case in cases if not case.has_commit]
    for case in cases:
        if not case.has_commit:
            continue
        constants = record_constants(case, source)
        write_constants(root / case.name, constants)
        print_info(
            MESSAGES.roadmap.stage_eval_record_case.format(
                name=case.name, constants=_constants_text(constants)
            )
        )
    if no_commit:
        print_error(MESSAGES.roadmap.stage_eval_record_no_commit.format(names=", ".join(no_commit)))
        raise typer.Exit(1)


def _replay(
    cases_dir: Path | None, names: tuple[str, ...], limit: int | None, *, as_json: bool
) -> None:
    from devops_cli.roadmap.stage.stage_eval_cases import load_cases, select_cases
    from devops_cli.roadmap.stage.stage_eval_gates import replay_all
    from devops_cli.roadmap.stage.stage_eval_render import render_replay, replay_json

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
    toolset: StageToolset | None,
    source: Path | None,
    dry_run: bool,
    as_json: bool,
    toolbox: bool,
) -> None:
    from devops_cli.ai.client import get_llm_client
    from devops_cli.ai.spend.ledger import observe_llm_calls
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.implement.implement_eval_run import eval_model
    from devops_cli.roadmap.intake.intake_model import gateway_address
    from devops_cli.roadmap.stage.stage_eval_cases import (
        cases_with_commit,
        left_out_note,
        load_cases,
        select_cases,
    )
    from devops_cli.roadmap.stage.stage_eval_render import (
        planned_calls,
        render_score,
        score_json,
    )
    from devops_cli.roadmap.stage.stage_eval_run import Outcome, run_cases
    from devops_cli.roadmap.stage.stage_eval_score import score_runs
    from devops_cli.roadmap.stage.stage_eval_usage import RunUsage

    cases, left_out = cases_with_commit(select_cases(load_cases(cases_dir), names, limit))
    settings = load_settings()
    chosen = toolset or settings.roadmap.stage.toolset
    gateway = gateway_address(settings.ai.for_task("stage"))
    if dry_run:
        render_request_plan(
            MESSAGES.roadmap.stage_eval_dry_run.format(
                gateway=gateway,
                cases=len(cases),
                mode=MESSAGES.roadmap.stage_eval_mode_toolbox
                if toolbox
                else MESSAGES.roadmap.stage_eval_mode_plain,
            ),
            planned_calls(cases, gateway, toolbox=toolbox),
            [note] if (note := left_out_note(left_out)) else [],
        )
        return
    client = get_llm_client(task="stage", settings=settings, model=model)
    name = model or settings.ai.for_task("stage").model
    planner = eval_model(model, task="stage")[0] if toolbox else None
    usage = RunUsage()
    with observe_llm_calls(usage.add):
        runs = run_cases(cases, client, source or find_repo_root(), toolbox=planner, toolset=chosen)
    score = score_runs(name, cases, runs, left_out=left_out, toolset=chosen)
    now = datetime.now(UTC)
    report = score_json(
        score, gateway=gateway, taken=now.isoformat(timespec="seconds"), usage=usage
    )
    target = resolve_store_path(f"{_STORE}/{now:%Y%m%dT%H%M%SZ}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    write_stdout(report if as_json else render_score(score, gateway=gateway, usage=usage))
    print_info(MESSAGES.roadmap.stage_eval_stored.format(path=target))
    failed = sum(run.outcome is Outcome.FAILED for run in runs)
    if failed:
        print_error(MESSAGES.roadmap.stage_eval_failed.format(failed=failed))
        raise typer.Exit(1)


def _compare(
    cases_dir: Path | None,
    names: tuple[str, ...],
    limit: int | None,
    *,
    toolsets: tuple[str, ...],
    runs: int,
    model: str | None,
    source: Path | None,
    dry_run: bool,
    verify: bool,
) -> None:
    """Compare the toolsets over the cases that `names` and `limit` pick, or state the plan of the
    comparison on a dry run."""
    from devops_cli.ai.client import get_llm_client
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.implement.implement_eval_run import eval_model
    from devops_cli.roadmap.intake.intake_model import gateway_address
    from devops_cli.roadmap.stage.stage_eval_cases import (
        cases_with_commit,
        left_out_note,
        load_cases,
        select_cases,
    )
    from devops_cli.roadmap.stage.stage_eval_compare import (
        estimated_spend,
        render_compare,
        run_toolset,
        toolsets_of,
    )

    if len(toolsets) < 2:
        raise ValidationError(MESSAGES.roadmap.stage_eval_compare_too_few, field="compare")
    chosen = toolsets_of(toolsets)
    cases, left_out = cases_with_commit(select_cases(load_cases(cases_dir), names, limit))
    settings = load_settings()
    name = model or settings.ai.for_task("stage").model
    gateway = gateway_address(settings.ai.for_task("stage"))
    note = left_out_note(left_out)
    if dry_run:
        plan = MESSAGES.roadmap.stage_eval_compare_dry_run.format(
            cases=len(cases),
            runs=runs,
            toolsets=", ".join(chosen),
            model=name,
            gateway=gateway,
        )
        estimate = estimated_spend(len(cases), runs, len(chosen), name)
        cost = (
            MESSAGES.roadmap.stage_eval_compare_dry_run_cost.format(cost=estimate)
            if estimate is not None
            else MESSAGES.roadmap.stage_eval_compare_dry_run_unpriced.format(model=name)
        )
        write_stdout(f"{plan}\n{cost}\n")
        if note:
            print_info(note)
        return
    client = get_llm_client(task="stage", settings=settings, model=model)
    planner = eval_model(model, task="stage")[0]
    verifier = eval_model(model, task="verification")[0] if verify else None
    rows = [
        run_toolset(
            toolset,
            cases,
            client,
            source or find_repo_root(),
            toolbox=planner,
            model=name,
            runs=runs,
            verifier=verifier,
        )
        for toolset in chosen
    ]
    write_stdout(render_compare(rows))
    if note:
        print_info(note)


@dry_run_class("request-plan")
def eval_stage_cmd(
    form: Annotated[list[str] | None, typer.Argument(help=HELP.roadmap.eval_stage_form)] = None,
    case: Annotated[
        list[str] | None, typer.Option("--case", help=HELP.roadmap.eval_stage_case)
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", help=HELP.roadmap.eval_stage_model)
    ] = None,
    toolset: Annotated[
        StageToolset | None, typer.Option("--toolset", help=HELP.roadmap.eval_stage_toolset)
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.eval_stage_limit)
    ] = None,
    runs: Annotated[int, typer.Option("--runs", min=1, help=HELP.roadmap.eval_stage_runs)] = 3,
    verify: Annotated[bool, typer.Option("--verify", help=HELP.roadmap.eval_stage_verify)] = False,
    as_json: Annotated[bool, typer.Option("--json", help=HELP.roadmap.eval_stage_json)] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_stage_dry_run)
    ] = False,
    replay: Annotated[bool, typer.Option("--replay", help=HELP.roadmap.eval_stage_replay)] = False,
    record: Annotated[
        bool,
        typer.Option(
            "--record",
            help="Write the constants that the plan of each case cites into its facts file.",
        ),
    ] = False,
    cases_dir: Annotated[
        Path | None, typer.Option("--cases", help=HELP.roadmap.eval_stage_cases)
    ] = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.eval_stage_source)
    ] = None,
    no_toolbox: Annotated[
        bool, typer.Option("--no-toolbox", help=HELP.roadmap.eval_stage_no_toolbox)
    ] = False,
) -> None:
    """Score the stage job on the golden set: the live run, or the replay through the gates."""
    names = tuple(case or ())
    words = tuple(form or ())
    if words:
        if words[0] != "compare":
            raise ValidationError(
                MESSAGES.roadmap.stage_eval_unknown_form.format(form=" ".join(words)), field="form"
            )
        _compare(
            cases_dir,
            names,
            limit,
            toolsets=words[1:],
            runs=runs,
            model=model,
            source=source,
            dry_run=dry_run or is_dry_run(),
            verify=verify,
        )
        return
    if record:
        if dry_run or is_dry_run():
            raise ValidationError(MESSAGES.roadmap.stage_eval_record_dry_run, field="record")
        _record(cases_dir, names, limit)
        return
    if replay:
        _replay(cases_dir, names, limit, as_json=as_json)
        return
    _run(
        cases_dir,
        names,
        limit,
        model=model,
        toolset=toolset,
        source=source,
        dry_run=dry_run or is_dry_run(),
        as_json=as_json,
        toolbox=not no_toolbox,
    )
