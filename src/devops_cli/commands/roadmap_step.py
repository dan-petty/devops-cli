"""`devops roadmap step`: the steps of the roadmap jobs, one command for each step (ADR 0021,
section 8). A step runs the same way as in the Service, and each command is a thin adapter of its
module under `devops_cli.roadmap.steps`. The group is defined here, each subcommand lives in its
own module and is registered here with one line, and `commands/roadmap.py` registers the group
once.
"""

from __future__ import annotations

from devops_cli.commands.roadmap_step_fix_checks import fix_checks_cmd
from devops_cli.commands.roadmap_step_fix_conflict import fix_conflict_cmd
from devops_cli.commands.roadmap_step_fix_plan import fix_plan_cmd
from devops_cli.commands.roadmap_step_infra_apply import infra_apply_cmd
from devops_cli.commands.roadmap_step_infra_plan import infra_plan_cmd
from devops_cli.commands.roadmap_step_open import open_cmd
from devops_cli.commands.roadmap_step_ready import ready_cmd
from devops_cli.commands.roadmap_step_review import review_cmd
from devops_cli.commands.roadmap_step_watch import watch_cmd
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

step_app = new_typer(help=HELP.roadmap.step_app, no_args_is_help=True)
step_app.command("fix-checks", help=HELP.roadmap.step_fix_checks)(fix_checks_cmd)
step_app.command("fix-conflict", help=HELP.roadmap.step_fix_conflict)(fix_conflict_cmd)
step_app.command("fix-plan", help=HELP.roadmap.step_fix_plan)(fix_plan_cmd)
step_app.command("infra-apply", help=HELP.roadmap.step_infra_apply)(infra_apply_cmd)
step_app.command("infra-plan", help=HELP.roadmap.step_infra_plan)(infra_plan_cmd)
step_app.command("open", help=HELP.roadmap.step_open)(open_cmd)
step_app.command("ready", help=HELP.roadmap.step_ready)(ready_cmd)
step_app.command("review", help=HELP.roadmap.step_review)(review_cmd)
step_app.command("watch", help=HELP.roadmap.step_watch)(watch_cmd)
