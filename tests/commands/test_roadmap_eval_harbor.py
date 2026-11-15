"""`devops roadmap eval harbor` (#3104): the export of the fixtures as task folders and the trials of
one task. The exporter and the run are tested in
`tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` and
`tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py`."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.roadmap_eval import case_data, write_fixture

Cli = Callable[..., Any]
TRIALS = 5
# The Coder harness of the Service, as Harbor loads a custom agent by its import path.
CODER_AGENT = "pydantic_ai_harness.coder:Coder"
REWARDS = (1.0, 0.0, 1.0, 1.0, 0.0)
COSTS = (0.1, 0.1, 0.1, 0.1, 0.1)
TASK_FILES = ("instruction.md", "environment/Dockerfile", "tests/test.sh", "task.toml")


@pytest.fixture
def fixtures(tmp_path: Path) -> Path:
    """A folder of two fixtures of the sample change."""
    root = tmp_path / "fixtures"
    root.mkdir()
    write_fixture(root, folder="a-case", case=case_data(name="a-case"))
    write_fixture(root, folder="b-case", case=case_data(name="b-case"))
    return root


def _export(cli: Cli, fixtures: Path, out: Path, *flags: str) -> Any:
    return cli(
        "roadmap",
        "eval",
        "harbor",
        "export",
        "--fixtures",
        str(fixtures),
        "--out",
        str(out),
        *flags,
    )


def _write_trials(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """Write the result of each trial into the job folder that the harbor call names."""
    jobs = Path(call.argv[call.argv.index("--jobs-dir") + 1])
    for index, (reward, cost) in enumerate(zip(REWARDS, COSTS, strict=True)):
        folder = jobs / "implement-eval" / f"a-case__{index:07d}"
        folder.mkdir(parents=True)
        result = {
            "verifier_result": {"rewards": {"reward": reward}},
            "agent_result": {"cost_usd": cost},
        }
        (folder / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return subprocess.CompletedProcess(args=list(call.argv), returncode=0, stdout="", stderr="")


def test_export_writes_a_task_folder_for_each_fixture(
    cli: Cli, fixtures: Path, tmp_path: Path
) -> None:
    out = tmp_path / "tasks"

    result = _export(cli, fixtures, out)

    assert result.exit_code == 0, result.output
    assert "Exported 2 Harbor task(s)" in result.stdout
    for name in ("a-case", "b-case"):
        folder = out / name
        assert [path for path in TASK_FILES if (folder / path).is_file()] == list(TASK_FILES)
        assert all((folder / path).read_text(encoding="utf-8").strip() for path in TASK_FILES)


def test_the_timeout_option_reaches_the_task_configuration(
    cli: Cli, fixtures: Path, tmp_path: Path
) -> None:
    out = tmp_path / "tasks"

    result = _export(cli, fixtures, out, "--fixture", "a-case", "--timeout", "900")

    assert result.exit_code == 0, result.output
    assert "timeout_sec = 900.0" in (out / "a-case" / "task.toml").read_text(encoding="utf-8")
    assert not (out / "b-case").exists()


def test_the_export_dry_run_writes_no_file(cli: Cli, fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "tasks"

    result = _export(cli, fixtures, out, "--dry-run")

    assert result.exit_code == 0, result.output
    assert not out.exists()
    assert "The export would write 2 task(s)" in result.stdout


def test_five_trials_of_one_task(
    cli: Cli, fixtures: Path, tmp_path: Path, process_fake: ProcessFake
) -> None:
    out = tmp_path / "tasks"
    assert _export(cli, fixtures, out, "--fixture", "a-case").exit_code == 0
    task = out / "a-case"
    process_fake.answer("harbor", ProcessAnswer(side_effect=_write_trials))

    result = cli(
        "roadmap",
        "eval",
        "harbor",
        "run",
        "--task",
        str(task),
        "--trials",
        str(TRIALS),
        "--agent",
        CODER_AGENT,
        "--provider",
        "docker",
    )

    assert result.exit_code == 0, result.output
    assert len(process_fake.calls) == 1
    argv = list(process_fake.calls[0].argv)
    assert argv[:2] == ["harbor", "run"]
    assert argv[argv.index("--n-attempts") + 1] == str(TRIALS)
    assert argv[argv.index("--path") + 1] == str(task)
    assert argv[argv.index("--agent") + 1] == CODER_AGENT
    assert argv[argv.index("--env") + 1] == "docker"
    reports = list(
        (resolve_data_path(load_settings().data.dir) / "eval" / "harbor").glob("*/result.json")
    )
    assert len(reports) == 1
    written = json.loads(reports[0].read_text(encoding="utf-8"))
    assert (written["pass_rate"], written["trial_count"]) == (0.6, TRIALS)
    assert "pass rate 0.60" in result.stdout
    assert f"Report: {reports[0]}" in result.stderr


def test_the_run_dry_run_starts_no_program(
    cli: Cli, fixtures: Path, tmp_path: Path, process_fake: ProcessFake
) -> None:
    out = tmp_path / "tasks"
    assert _export(cli, fixtures, out, "--fixture", "a-case").exit_code == 0

    result = cli(
        "roadmap",
        "eval",
        "harbor",
        "run",
        "--task",
        str(out / "a-case"),
        "--trials",
        str(TRIALS),
        "--dry-run",
    )

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert "--n-attempts 5" in result.stdout
