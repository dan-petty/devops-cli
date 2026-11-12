"""`devops roadmap step`: the steps of the roadmap jobs, one command for each step (ADR 0021,
section 8). A step runs the same way as in the Service, and each command is a thin adapter of its
module under `devops_cli.roadmap.steps`. The group is defined here, each subcommand lives in its
own module and is registered here with one line, and `commands/roadmap.py` registers the group
once.
"""

from __future__ import annotations

from devops_cli.commands.roadmap_step_fix_plan import fix_plan_cmd
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

step_app = new_typer(help=HELP.roadmap.step_app, no_args_is_help=True)
step_app.command("fix-plan", help=HELP.roadmap.step_fix_plan)(fix_plan_cmd)
