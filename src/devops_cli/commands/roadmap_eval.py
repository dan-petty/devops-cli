"""`devops roadmap eval`: the golden sets that measure the plan and implement jobs (#3027).

A subcommand of this group runs a job's real code on a committed set of cases with a chosen model,
prints a score and stores it under `.data/`. Each is an on-demand command and no part of
`devops ci`: it calls the model through the gateway. Its `--replay` mode calls no model. The
group is defined here, and each subcommand lives in its own module and is registered here with one
line. `commands/roadmap.py` registers the group once.
"""

from __future__ import annotations

from devops_cli.commands.roadmap_eval_stage import eval_stage_cmd
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

eval_app = new_typer(help=HELP.roadmap.eval_app, no_args_is_help=True)
eval_app.command("stage", help=HELP.roadmap.eval_stage)(eval_stage_cmd)
