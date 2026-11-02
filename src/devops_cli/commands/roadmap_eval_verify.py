"""`devops roadmap eval verify`: the verification pass of the stage job on its golden set (#3153).

The command runs the pass on each case of `tests/fixtures/roadmap_eval/stage/` with the model of
the `verification` task, or with `--model`, and prints the recall of the labeled defects and the
findings on the good plans. It stores the score as JSON under the data directory.
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

_STORE = "roadmap_eval/verify"
_TASK = "verification"


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
    from devops_cli.roadmap.stage_verify_eval import (
        evaluate_cases,
        planned_verify_calls,
        render_verify,
        verify_json,
    )

    cases = select_cases(load_cases(cases_dir), names, limit)
    settings = load_settings()
    gateway = gateway_address(settings.ai)
    if dry_run:
        render_request_plan(
            MESSAGES.roadmap.verify_eval_dry_run.format(gateway=gateway, cases=len(cases)),
            planned_verify_calls(cases, gateway),
        )
        return
    client = get_llm_client(task=_TASK, settings=settings, model=model)
    name = model or settings.ai.for_task(_TASK).model
    score = evaluate_cases(name, cases, client, source or find_repo_root())
    now = datetime.now(UTC)
    report = verify_json(score, gateway=gateway, taken=now.isoformat(timespec="seconds"))
    target = resolve_store_path(f"{_STORE}/{now:%Y%m%dT%H%M%SZ}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
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
) -> None:
    """Score the verification pass on the golden set of the stage job."""
    _run(
        cases_dir,
        tuple(case or ()),
        limit,
        model=model,
        source=source,
        dry_run=dry_run or is_dry_run(),
        as_json=as_json,
    )
