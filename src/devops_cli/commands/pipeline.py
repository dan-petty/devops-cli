"""Programmable containerized pipeline execution engine via Dagger."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import BIN_DAGGER, build_dagger_cmd
from devops_cli.config.constants import CONST_CURRENT_DIR
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success
from devops_cli.telemetry.tracer import trace_span

app = new_typer(help=HELP.pipeline.app, no_args_is_help=True)


@app.command("run", help=HELP.pipeline.run)
def run_pipeline_cmd(
    pipeline_path: Annotated[
        Path,
        typer.Argument(help=HELP.pipeline.pipeline_path),
    ] = CONST_CURRENT_DIR,
    function_name: Annotated[
        str | None,
        typer.Option("--function", "-f", help=HELP.pipeline.function_name),
    ] = None,
    args: Annotated[
        list[str] | None,
        typer.Option("--args", "-a", help=HELP.pipeline.args),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Execute reproducible, containerized developer pipelines with Dagger."""
    if not pipeline_path.exists():
        safe_path = pipeline_path.name or str(pipeline_path)
        print_error(f"Pipeline path does not exist: {safe_path}", prefix=False)
        raise typer.Exit(1)

    if function_name is not None:
        import re

        if not re.match(r"^[a-zA-Z0-9_\-]+$", function_name):
            print_error(
                f"Invalid function name '{function_name}': contains unsafe characters.",
                prefix=False,
            )
            raise typer.Exit(1)

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops pipeline run",
            action="execute_dagger_pipeline",
            details={
                "pipeline_path": str(pipeline_path),
                "function_name": function_name or "default",
                "args": args or [],
                "status": "SIMULATED_SUCCESS",
            },
        )
        return

    with trace_span("pipeline.run", attributes={"pipeline_path": str(pipeline_path)}):
        has_dagger = check_binary(BIN_DAGGER)
        if not has_dagger:
            print_error(
                MESSAGES.pipeline.dagger_not_found,
                prefix=False,
            )
            raise typer.Exit(1)

        print_info(
            MESSAGES.pipeline.executing.format(path=str(pipeline_path)),
            prefix=False,
        )
        cmd = build_dagger_cmd(
            pipeline_path=pipeline_path.resolve(),
            function_name=function_name,
            args=args,
        )
        res = run_subprocess(cmd, check=False)
        if res.returncode == 0:
            print_success(MESSAGES.pipeline.success.format(name=pipeline_path.name))
        else:
            print_error(
                MESSAGES.pipeline.failed.format(code=res.returncode),
                prefix=False,
            )
            raise typer.Exit(res.returncode)
