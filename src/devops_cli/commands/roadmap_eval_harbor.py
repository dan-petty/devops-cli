"""`devops roadmap eval harbor` (#3104): the implement fixtures as Harbor tasks and their trials.

`export` writes one Harbor task folder for each chosen fixture of `devops roadmap eval implement`,
so another harness runs the fixture and its numbers compare with those of another agent. `run` runs
N trials of one task folder with the harbor program, and writes the pass rate and the cost of the
run under the data directory. Both are on-demand commands and no part of `devops ci`. The harbor
program and the Docker engine go through the process seam, so a test starts neither.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.config.constants import CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES
from devops_cli.config.defaults import DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root, resolve_store_path
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run, render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_muted, write_stdout
from devops_cli.output.serialization import emit_serialized

if TYPE_CHECKING:
    from devops_cli.roadmap.implement.implement_eval import LoadedCase
    from devops_cli.roadmap.implement.implement_eval_harbor_run import HarborReport

harbor_app = new_typer(help=HELP.roadmap.eval_harbor_app, no_args_is_help=True)


def _chosen_cases(fixtures: Path | None, names: list[str] | None) -> list[LoadedCase]:
    """The chosen fixtures of the fixture folder, or of the committed fixtures of this checkout."""
    from devops_cli.roadmap.implement.implement_eval import choose_cases, load_cases

    root = fixtures or find_repo_root() / CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES
    return list(choose_cases(load_cases(root), tuple(names or ())))


def _export_root(out: Path | None) -> Path:
    """The folder of the task folders: the given one, or the one under the data directory."""
    return resolve_store_path("eval/harbor/tasks", out)


def _plan_export(names: list[str], root: Path) -> None:
    """Print the task folders that an export would write, and write none."""
    write_stdout(
        MESSAGES.roadmap.eval_harbor_export_dry_title.format(count=len(names), path=root) + "\n"
    )
    for name in names:
        write_stdout(
            MESSAGES.roadmap.eval_harbor_export_task.format(name=name, path=root / name) + "\n"
        )


def _emit_export(exported: list[Path], root: Path, *, as_json: bool) -> None:
    """Print the task folders that the export wrote, as text or as JSON."""
    if as_json:
        emit_serialized(
            {
                "out": str(root),
                "tasks": [{"name": folder.name, "path": str(folder)} for folder in exported],
            },
            "json",
        )
        return
    write_stdout(
        MESSAGES.roadmap.eval_harbor_export_title.format(count=len(exported), path=root) + "\n"
    )
    for folder in exported:
        write_stdout(
            MESSAGES.roadmap.eval_harbor_export_task.format(name=folder.name, path=folder) + "\n"
        )


def _plan_run(task: Path, trials: int, agent: str, model: str, provider: str) -> None:
    """Print the harbor command that a run would start, and start none."""
    from devops_cli.roadmap.implement.implement_eval_harbor_run import harbor_argv

    argv = harbor_argv(task, trials, agent, model, provider, Path("<jobs-dir>"))
    render_request_plan(
        MESSAGES.roadmap.eval_harbor_dry_run,
        [PlannedRequest(method="PROCESS", target=str(task), argv=tuple(argv))],
    )


def _render_run(report: HarborReport) -> None:
    """Print the report of a run: its pass rate, its cost and the reward of each trial."""
    write_stdout(
        MESSAGES.roadmap.eval_harbor_run_title.format(
            pass_rate=report.pass_rate, trials=report.trial_count, cost=report.total_cost_usd
        )
        + "\n"
    )
    for number, reward in enumerate(report.rewards, start=1):
        write_stdout(
            MESSAGES.roadmap.eval_harbor_run_reward.format(number=number, reward=reward) + "\n"
        )


@dry_run_class("no-external-request")
def export_cmd(
    fixture: Annotated[
        list[str] | None, typer.Option("--fixture", "-F", help=HELP.roadmap.eval_harbor_fixture)
    ] = None,
    fixtures: Annotated[
        Path | None, typer.Option("--fixtures", help=HELP.roadmap.eval_harbor_fixtures)
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", help=HELP.roadmap.eval_harbor_out)] = None,
    timeout: Annotated[
        int, typer.Option("--timeout", min=1, help=HELP.roadmap.eval_harbor_timeout)
    ] = DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS,
    json_output: Annotated[
        bool, typer.Option("--json", help=HELP.roadmap.eval_harbor_json)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_harbor_export_dry_run)
    ] = False,
) -> None:
    """Export each chosen implement fixture as a Harbor task folder."""
    from devops_cli.roadmap.implement.implement_eval_harbor import export_task

    cases = _chosen_cases(fixtures, fixture)
    root = _export_root(out)
    if dry_run or is_dry_run():
        _plan_export([case.name for case in cases], root)
        return
    exported = [export_task(case, root / case.name, timeout_seconds=timeout) for case in cases]
    _emit_export(exported, root, as_json=json_output)


@dry_run_class("request-plan")
def run_cmd(
    task: Annotated[Path, typer.Option("--task", help=HELP.roadmap.eval_harbor_task)],
    trials: Annotated[
        int, typer.Option("--trials", min=1, help=HELP.roadmap.eval_harbor_trials)
    ] = 1,
    agent: Annotated[
        str | None, typer.Option("--agent", help=HELP.roadmap.eval_harbor_agent)
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", help=HELP.roadmap.eval_harbor_model)
    ] = None,
    provider: Annotated[
        str | None, typer.Option("--provider", help=HELP.roadmap.eval_harbor_provider)
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help=HELP.roadmap.eval_harbor_json)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.eval_harbor_run_dry_run)
    ] = False,
) -> None:
    """Run the trials of one Harbor task, and write the pass rate and the cost."""
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    chosen_agent = agent or run.DEFAULT_AGENT
    chosen_model = model or run.DEFAULT_MODEL
    chosen_provider = provider or run.DEFAULT_PROVIDER
    if dry_run or is_dry_run():
        _plan_run(task, trials, chosen_agent, chosen_model, chosen_provider)
        return
    out = run.run_directory(datetime.now(UTC))
    report = run.run_trials(task, trials, chosen_agent, chosen_model, chosen_provider, out)
    if json_output:
        write_stdout(report.model_dump_json(indent=2) + "\n")
    else:
        _render_run(report)
    print_muted(
        MESSAGES.roadmap.eval_harbor_run_saved.format(path=out / run.REPORT_FILE), to_stderr=True
    )


harbor_app.command("export", help=HELP.roadmap.eval_harbor_export)(export_cmd)
harbor_app.command("run", help=HELP.roadmap.eval_harbor_run)(run_cmd)
