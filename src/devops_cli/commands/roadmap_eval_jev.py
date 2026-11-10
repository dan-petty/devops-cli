"""`devops roadmap eval jev`: Jev against the triage model on intake's proposal fields (#4298).

The command runs the duplicate cases and the label cases through both models and prints the false
duplicates of each first. It writes nothing to GitHub, and it stops before the first call when the
run needs more calls than `--max-calls`, which bounds the spend.
"""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.config.constants import CONST_AI_JEV_MODEL, CONST_ROADMAP_JEV_EVAL_MAX_CALLS
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, write_stdout
from devops_cli.roadmap.intake.intake_requests import SpendMeter


@dry_run_class("request-plan")
def jev_cmd(
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.eval_jev_dry_run)] = False,
    max_calls: Annotated[
        int, typer.Option("--max-calls", min=1, help=HELP.roadmap.eval_jev_max_calls)
    ] = CONST_ROADMAP_JEV_EVAL_MAX_CALLS,
    min_confidence: Annotated[
        float,
        typer.Option("--min-confidence", min=0.0, max=1.0, help=HELP.roadmap.eval_jev_confidence),
    ] = 0.0,
) -> None:
    """Compare Jev with the triage model on the duplicate cases and the label cases."""
    from devops_cli.config.settings import get_ai_api_key, load_settings
    from devops_cli.roadmap import duplicate_eval, jev_eval
    from devops_cli.roadmap.intake.intake_jev import JevIntakeModel
    from devops_cli.roadmap.intake.intake_model import GatewayIntakeModel, gateway_address

    settings = load_settings()
    gateway_text = gateway_address(settings.ai)
    duplicates, labelled = duplicate_eval.load_cases(), jev_eval.load_label_cases()
    calls = jev_eval.planned_calls(len(duplicates), len(labelled))
    if calls > max_calls:
        print_error(MESSAGES.roadmap.jev_compare_over_limit.format(calls=calls, limit=max_calls))
        raise typer.Exit(2)
    if dry_run or is_dry_run():
        write_stdout(
            jev_eval.render_dry_run(
                duplicate_cases=len(duplicates),
                label_cases=len(labelled),
                gateway=gateway_text,
                limit=max_calls,
            )
        )
        return
    labels = duplicate_eval.checkout_labels()
    gateway = GatewayIntakeModel(
        settings.ai, api_key=get_ai_api_key(settings), embedder=duplicate_eval.SameVector()
    )
    triage_meter, jev_meter = SpendMeter(), SpendMeter()
    triage = triage_meter.model(gateway)
    jev = jev_meter.model(
        JevIntakeModel(gateway, settings=settings, fall_back=False, min_confidence=min_confidence)
    )
    scores = [
        jev_eval.ModelScores(
            name=name,
            duplicates=duplicate_eval.evaluate_duplicates(duplicates, model, labels),
            labels=jev_eval.evaluate_labels(labelled, model, labels),
        )
        for name, model in (
            (settings.ai.for_task("triage").model, triage),
            (CONST_AI_JEV_MODEL, jev),
        )
    ]
    spend = triage_meter.spend()
    spent = MESSAGES.roadmap.jev_compare_spent.format(
        triage=spend.model_calls,
        jev=jev_meter.counts["model_calls"],
        github=spend.rest + spend.search + spend.graphql,
    )
    write_stdout(
        jev_eval.render_comparison(
            scores,
            duplicate_cases=len(duplicates),
            label_cases=len(labelled),
            spend=spent,
            least=min_confidence,
        )
    )
