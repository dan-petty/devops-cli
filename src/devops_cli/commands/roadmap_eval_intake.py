"""`devops roadmap eval intake`: the duplicate judgement of intake on its evaluation set (#1989).

The command runs each case of the set through intake with the configured analysis model and
prints whether intake agrees with the verdict of a person. It writes nothing to GitHub.
"""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, write_stdout
from devops_cli.roadmap.intake.intake_requests import SpendMeter


@dry_run_class("request-plan")
def intake_cmd(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_intake_dry_run)
    ] = False,
) -> None:
    """Score intake's duplicate judgement against the evaluation set."""
    from devops_cli.config.settings import get_ai_api_key, load_settings
    from devops_cli.roadmap import duplicate_eval
    from devops_cli.roadmap.intake.intake_model import GatewayIntakeModel, gateway_address

    cases = duplicate_eval.load_cases()
    settings = load_settings()
    gateway = gateway_address(settings.ai)
    if dry_run or is_dry_run():
        write_stdout(duplicate_eval.render_duplicate_dry_run(cases, gateway=gateway))
        return
    labels = duplicate_eval.checkout_labels()
    meter = SpendMeter()
    intake_model = GatewayIntakeModel(
        settings.ai, api_key=get_ai_api_key(settings), embedder=duplicate_eval.SameVector()
    )
    score = duplicate_eval.evaluate_duplicates(cases, meter.model(intake_model), labels)
    model = settings.ai.for_task("analysis").model
    spend = meter.spend()
    spent = MESSAGES.roadmap.intake_eval_spent.format(
        calls=spend.model_calls, github=spend.rest + spend.search + spend.graphql
    )
    report = duplicate_eval.render_duplicate_score(score, model=model, gateway=gateway, spend=spent)
    write_stdout(report)
    if score.failed:
        print_error(MESSAGES.roadmap.intake_eval_failed.format(failed=score.failed))
        raise typer.Exit(1)
