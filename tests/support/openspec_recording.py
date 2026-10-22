"""The real OpenSpec's answers, recorded over the scenarios, which `OpenSpecFake` replays (#1844).

`record_scenarios` builds each scenario of `tests/support/openspec_scenarios.py` in a scratch
directory and runs the gate over it with the real tool, keeping every `openspec` run: its
arguments, exit code, standard output and standard error. A run's text names the directory it ran
in, which differs on every recording, so the record holds `{cwd}` in its place. A scenario's runs
that equal the `empty` scenario's, such as `config set` and `update --force`, are kept once, in
`empty`, and the fake falls back to them.

Record again when the pin in `tools.lock` changes, or a command the gate runs does, with the
pinned `openspec` on PATH (`uv run devops install-tools --tool openspec --only-missing`):

    uv run python -c "from tests.support.openspec_recording import record_scenarios; record_scenarios()"

`tests/test_openspec_contract.py` fails until the record is of the locked version.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.support.openspec_scenarios import SCENARIOS, build_scenario

# The scenario every other scenario falls back to for a run it does not hold itself.
BASE_SCENARIO = "empty"
_CWD = "{cwd}"
_RECORD = files("tests").joinpath("fixtures", "openspec_runs", "recorded_runs.json")


@dataclass(frozen=True)
class RecordedRun:
    """One `openspec` run: what it was given after the program name, and what it answered."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def load_recorded_runs() -> tuple[str, dict[str, dict[tuple[str, ...], RecordedRun]]]:
    """The version of the tool that was recorded, and each scenario's runs by their arguments."""
    record: dict[str, Any] = json.loads(_RECORD.read_text(encoding="utf-8"))
    scenarios = {
        name: {
            tuple(run["argv"]): RecordedRun(
                tuple(run["argv"]), run["returncode"], run["stdout"], run["stderr"]
            )
            for run in runs
        }
        for name, runs in record["scenarios"].items()
    }
    return record["version"], scenarios


def _with_placeholder(text: str, cwd: Path) -> str:
    """`text`, with the directory the run ran in written as the placeholder."""
    return text.replace(str(cwd), _CWD)


def _record_gate(tree: Path) -> list[dict[str, Any]]:
    """Every `openspec` run the gate makes over `tree`, as the record holds it."""
    from devops_cli.openspec.gate import check_openspec

    real_run = subprocess.run
    runs: list[dict[str, Any]] = []

    def recording_run(args: Any, *popenargs: Any, **kwargs: Any) -> Any:
        completed = real_run(args, *popenargs, **kwargs)
        if Path(args[0]).name == "openspec":
            cwd = Path(kwargs["cwd"])
            runs.append(
                {
                    "argv": list(args[1:]),
                    "returncode": completed.returncode,
                    "stdout": _with_placeholder(completed.stdout, cwd),
                    "stderr": _with_placeholder(completed.stderr, cwd),
                }
            )
        return completed

    with patch.object(subprocess, "run", recording_run):
        check_openspec(tree)
    return runs


def record_scenarios(destination: Path | None = None) -> None:
    """Run the gate over every scenario with the real `openspec` on PATH and write the record to
    `destination`, by default the committed one."""
    version = subprocess.run(
        ["openspec", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    committed_skills = Path(str(files("tests"))).parent
    recorded: dict[str, list[dict[str, Any]]] = {}
    for name in SCENARIOS:
        with tempfile.TemporaryDirectory(prefix="openspec-scenario-") as scratch:
            tree = Path(scratch) / "tree"
            tree.mkdir()
            build_scenario(name, tree, committed_skills)
            recorded[name] = _record_gate(tree)
    base = {tuple(run["argv"]): run for run in recorded[BASE_SCENARIO]}
    scenarios = {
        name: [run for run in runs if name == BASE_SCENARIO or base.get(tuple(run["argv"])) != run]
        for name, runs in recorded.items()
    }
    target = destination or Path(str(_RECORD))
    target.write_text(
        json.dumps({"version": version, "scenarios": scenarios}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
