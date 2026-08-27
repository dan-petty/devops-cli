"""Programmable containerized pipeline execution engine via Dagger."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import BIN_DAGGER, build_dagger_cmd
from devops_cli.config.constants import CONST_CURRENT_DIR
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.output import print_error, print_info, print_success
from devops_cli.telemetry.tracer import trace_span

app = new_typer(help="Programmable containerized pipeline execution.", no_args_is_help=True)


@app.command("run")
def run_pipeline_cmd(
    pipeline_path: Annotated[
        Path,
        typer.Argument(help="Path to Dagger module directory or pipeline script"),
    ] = CONST_CURRENT_DIR,
    function_name: Annotated[
        str | None,
        typer.Option("--function", "-f", help="Target pipeline function to call"),
    ] = None,
    args: Annotated[
        list[str] | None,
        typer.Option("--args", "-a", help="Arguments to forward to the pipeline execution"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate pipeline execution"),
    ] = False,
) -> None:
    """Execute reproducible, containerized developer pipelines with Dagger."""
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
        has_dagger = shutil.which(BIN_DAGGER) is not None
        if not has_dagger:
            print_error(
                "Dagger CLI binary not found in PATH. Install Dagger to run containerized pipelines.",
                prefix=False,
            )
            raise typer.Exit(1)

        print_info(f"Executing Dagger pipeline from '{pipeline_path}'...", prefix=False)
        cmd = build_dagger_cmd(
            pipeline_path=pipeline_path.resolve(),
            function_name=function_name,
            args=args,
        )
        res = run_subprocess(cmd, check=False)
        if res.returncode == 0:
            print_success(f"✓ Pipeline execution completed successfully ({pipeline_path.name}).")
        else:
            print_error(f"Pipeline execution failed with exit code {res.returncode}.", prefix=False)
            raise typer.Exit(res.returncode)
