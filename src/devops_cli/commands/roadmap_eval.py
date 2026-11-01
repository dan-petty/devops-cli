"""`devops roadmap eval`: the group of the commands that measure a roadmap job (#3030).

This module only defines the group and lists its commands, so a new command adds an import and one
line. `devops roadmap` adds the group once.
"""

from __future__ import annotations

from devops_cli.commands.roadmap_eval_implement import implement_cmd
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

app = new_typer(help=HELP.roadmap.eval_app, no_args_is_help=True)

app.command("implement", help=HELP.roadmap.eval_implement)(implement_cmd)
