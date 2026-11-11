"""`devops roadmap eval verify`: the verification pass of the stage job on its golden set (#3153).

The command runs the pass on each case of `tests/fixtures/roadmap_eval/stage/` with the model of
the `verification` task, or with `--model`, and prints the recall of the labeled defects and the
findings on the good plans. It stores the score as JSON in a new file of its own under the data
directory, also when another run starts in the same second (#4488), and writes the file again when
each case ends. `--resume` takes such a file, runs only the cases that the file lacks or that
failed in it, and updates the file in place (#4344).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from devops_cli.core.repo import create_store_file, find_repo_root
from devops_cli.dry_run import dry_run_class, is_dry_run, render_request_plan
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, write_stdout, write_text_file

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings
    from devops_cli.roadmap.stage.stage_eval_cases import StageCase
    from devops_cli.roadmap.stage.stage_verify_eval import CaseOutcome

_STORE = "roadmap_eval/verify"
_TASK = "verification"


def _review_model(settings: Settings, model: str | None) -> Any:
    """The pydantic-ai model of the review: the model of the task `verification`, or `--model` in
    its place with the rest of the task, such as its provider and its sampling (#3039). The review
    reads the repository with the read tools, so it needs this model and not only the client of
    the task."""
    from devops_cli.ai.client.factory import get_task_model

    if model is None:
        return get_task_model(_TASK, settings=settings)
    override = settings.ai.tasks.verification.model_copy(update={"model": model})
    tasks = settings.ai.tasks.model_copy(update={_TASK: override})
    ai = settings.ai.model_copy(update={"tasks": tasks})
    return get_task_model(_TASK, settings=settings.model_copy(update={"ai": ai}))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _with_stored(
    every: list[StageCase], chosen: list[StageCase], stored: tuple[CaseOutcome, ...], path: Path
) -> list[StageCase]:
    """The cases that `names` and `limit` chose, and each case that the resumed report holds, in
    the order of the set, so that the report keeps every case it held. A case of the report that
    the set lacks raises `ConfigurationError`."""
    held = {outcome.name for outcome in stored}
    if lacking := sorted(held - {case.name for case in every}):
        raise ConfigurationError(
            MESSAGES.roadmap.verify_eval_resume_unknown.format(path=path, names=", ".join(lacking)),
            details={"path": str(path), "cases": lacking},
        )
    names = held | {case.name for case in chosen}
    return [case for case in every if case.name in names]


def _run(
    cases_dir: Path | None,
    names: tuple[str, ...],
    limit: int | None,
    *,
    model: str | None,
    source: Path | None,
    resume: Path | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    from devops_cli.ai.client import get_llm_client
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.intake.intake_model import gateway_address
    from devops_cli.roadmap.stage.stage_eval_cases import (
        cases_with_commit,
        left_out_note,
        load_cases,
        select_cases,
    )
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
    from devops_cli.roadmap.stage.stage_verify_eval import (
        evaluate_cases,
        pending_cases,
        planned_verify_calls,
        render_verify,
        resumed_outcomes,
        verify_json,
    )

    settings = load_settings()
    name = model or settings.ai.for_task(_TASK).model
    every = load_cases(cases_dir)
    chosen = select_cases(every, names, limit)
    done: tuple[CaseOutcome, ...] = ()
    if resume is not None:
        done = resumed_outcomes(resume, name)
        chosen = _with_stored(every, chosen, done, resume)
    cases, left_out = cases_with_commit(chosen)
    gateway = gateway_address(settings.ai)
    if dry_run:
        pending = pending_cases(cases, done)
        render_request_plan(
            MESSAGES.roadmap.verify_eval_dry_run.format(gateway=gateway, cases=len(pending)),
            planned_verify_calls(pending, gateway),
            [note] if (note := left_out_note(left_out)) else [],
        )
        return
    client = get_llm_client(task=_TASK, settings=settings, model=model)
    review = ToolboxModel(_review_model(settings, model))
    target = resume or create_store_file(_STORE)
    print_info(MESSAGES.roadmap.verify_eval_storing.format(path=target))
    score = evaluate_cases(
        name,
        cases,
        client,
        source or find_repo_root(),
        toolbox=review,
        left_out=left_out,
        done=done,
        store=lambda ended: write_text_file(
            target, verify_json(ended, gateway=gateway, taken=_now())
        ),
    )
    report = verify_json(score, gateway=gateway, taken=_now())
    write_text_file(target, report)
    write_stdout(report if as_json else render_verify(score, gateway=gateway))
    print_info(MESSAGES.roadmap.stage_eval_stored.format(path=target))
    if score.failed:
        print_error(MESSAGES.roadmap.verify_eval_failed.format(failed=score.failed))
        raise typer.Exit(1)


@dry_run_class("request-plan")
def verify_cmd(
    case: Annotated[
        list[str] | None, typer.Option("--case", help=HELP.roadmap.eval_stage_case)
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", help=HELP.roadmap.eval_verify_model)
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.eval_stage_limit)
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help=HELP.roadmap.eval_stage_json)] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_stage_dry_run)
    ] = False,
    cases_dir: Annotated[
        Path | None, typer.Option("--cases", help=HELP.roadmap.eval_stage_cases)
    ] = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.eval_stage_source)
    ] = None,
    resume: Annotated[
        Path | None,
        typer.Option("--resume", exists=True, dir_okay=False, help=HELP.roadmap.eval_verify_resume),
    ] = None,
) -> None:
    """Score the verification pass on the golden set of the stage job."""
    _run(
        cases_dir,
        tuple(case or ()),
        limit,
        model=model,
        source=source,
        resume=resume,
        dry_run=dry_run or is_dry_run(),
        as_json=as_json,
    )
