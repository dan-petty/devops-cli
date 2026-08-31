"""Load testing and service benchmark command group."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.commands import BIN_K6, build_k6_cmd
from devops_cli.config.constants import CONST_CURRENT_DIR
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success
from devops_cli.telemetry.tracer import trace_span

app = new_typer(help=HELP.test.app, no_args_is_help=True)


@app.command("load")
def load_test_cmd(
    script_path: Annotated[
        Path,
        typer.Argument(help=HELP.test.script_path),
    ] = CONST_CURRENT_DIR / "tests" / "load" / "smoke_test.js",
    vus: Annotated[
        int,
        typer.Option("--vus", "-u", help=HELP.test.vus),
    ] = 10,
    duration: Annotated[
        str,
        typer.Option("--duration", "-d", help=HELP.test.duration),
    ] = "30s",
    summary_export: Annotated[
        Path | None,
        typer.Option("--summary-export", "-s", help=HELP.test.summary_export),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.test.dry_run),
    ] = False,
) -> None:
    """Execute developer-centric load, spike, and latency tests against services using k6."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops test load",
            action="execute_k6_load_test",
            details={
                "script_path": str(script_path),
                "vus": vus,
                "duration": duration,
                "summary_export": str(summary_export) if summary_export else None,
                "simulated_metrics": {
                    "http_reqs": vus * 50,
                    "http_req_duration_p95_ms": 14.2,
                    "http_req_failed_rate": 0.0,
                },
            },
        )
        return

    with trace_span("test.load", attributes={"vus": vus, "duration": duration}):
        has_k6 = shutil.which(BIN_K6) is not None
        if not has_k6:
            print_error(
                ERRORS.test.k6_not_found,
                prefix=False,
            )
            raise typer.Exit(1)

        print_info(
            MESSAGES.test.starting_load_test.format(
                vus=vus, duration=duration, script_path=script_path
            ),
            prefix=False,
        )
        cmd = build_k6_cmd(
            script_path=script_path.resolve(),
            vus=vus,
            duration=duration,
            summary_export=summary_export.resolve() if summary_export else None,
        )
        res = run_subprocess(cmd, check=False)
        if res.returncode == 0:
            print_success(MESSAGES.test.load_test_success.format(duration=duration, vus=vus))
        else:
            print_error(MESSAGES.test.load_test_failed.format(code=res.returncode), prefix=False)
            raise typer.Exit(res.returncode)
