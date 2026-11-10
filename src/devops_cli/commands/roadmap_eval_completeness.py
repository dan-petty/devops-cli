"""`devops roadmap eval completeness`: the Jev completeness check on its labelled set (#4308).

The command asks Jev about each case of `tests/fixtures/roadmap_eval/completeness/` and prints the
recall of the incomplete drafts and the false holds on the complete ones. It stores the report as
JSON under the data directory. With `--dry-run` it makes no request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.repo import resolve_store_path
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_info, write_stdout

_STORE = "roadmap_eval/completeness"


def _run(cases_dir: Path | None, limit: int | None, *, dry_run: bool, as_json: bool) -> None:
    from devops_cli.ai.jev import create_jev_model
    from devops_cli.config.constants import CONST_AI_JEV_MODEL
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.intake.intake_model import gateway_address
    from devops_cli.roadmap.jev_completeness_eval import (
        load_cases,
        render,
        report_json,
        run_cases,
    )

    cases = load_cases(cases_dir)[:limit]
    settings = load_settings()
    gateway = gateway_address(settings.ai)
    if dry_run:
        texts = MESSAGES.roadmap
        render_request_plan(
            texts.jev_eval_dry_run.format(gateway=gateway, cases=len(cases)),
            [
                PlannedRequest(
                    method="POST",
                    target=f"{gateway}/systemone",
                    stdin=texts.jev_eval_dry_run_case.format(name=case.id),
                    repeat=texts.jev_eval_dry_run_repeat,
                )
                for case in cases
            ],
            [],
        )
        return
    results = run_cases(cases, new_model=lambda: create_jev_model(settings=settings))
    now = datetime.now(UTC)
    report = report_json(
        results, model=CONST_AI_JEV_MODEL, gateway=gateway, taken=now.isoformat(timespec="seconds")
    )
    target = resolve_store_path(f"{_STORE}/{now:%Y%m%dT%H%M%SZ}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    write_stdout(report if as_json else render(results, model=CONST_AI_JEV_MODEL, gateway=gateway))
    print_info(MESSAGES.roadmap.jev_eval_stored.format(path=target))


@dry_run_class("request-plan")
def completeness_cmd(
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.eval_stage_limit)
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help=HELP.roadmap.eval_stage_json)] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_stage_dry_run)
    ] = False,
    cases_dir: Annotated[
        Path | None, typer.Option("--cases", help=HELP.roadmap.eval_completeness_cases)
    ] = None,
) -> None:
    """Score the Jev completeness check on its labelled set."""
    _run(cases_dir, limit, dry_run=dry_run or is_dry_run(), as_json=as_json)
