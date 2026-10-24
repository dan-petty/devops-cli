"""The OpenSpec the gate starts, faked at the process edge, and the `openspec_fake` fixture that
installs the fake (#1844, ADR 0007).

The process edge has no seam yet (#775), so the fake doubles the stdlib objects themselves:
`shutil.which` finds `openspec` under `bin_dir` while the fake is installed, and `subprocess.run`,
through which `run_subprocess` starts every program, answers an `openspec` command from the record
of the real tool, starting nothing. Every other command, git among them,
is found and run for real, under the suite's refusal of every program but git, bwrap and kubectl's
offline renderers.

The record (`tests/fixtures/openspec_runs/recorded_runs.json`, made by
`tests/support/openspec_recording.py`) holds the real, pinned tool's answers to the commands the
gate and `devops openspec archive` run, over each scenario of `tests/support/openspec_scenarios.py`.
`tree` builds a scenario for a test and selects its runs. A command the record does not hold for
the scenario fails the test, naming the command, so a change to the commands the code starts fails
here until the record is made again. The fake does two things beyond replaying. A test may script
a command's answer (`script`) or make it hang (`hang`), for the failures a recording cannot hold: a
tool that dies with no JSON, or that runs past its timeout. And it writes what `openspec update
--force` writes, in each agent's tree that already holds a skill: the skills the repository
commits, which are the real tool's output at the pin, and it removes every other skill of
OpenSpec's, as the real tool removes a workflow the profile does not hold (tried: 1.14.3 removed a
hand-made `openspec-archive-change`). `calls` holds every command the fake answered, with the
directory and the OpenSpec environment it was started with.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from tests.support.openspec_recording import BASE_SCENARIO, RecordedRun, load_recorded_runs
from tests.support.openspec_scenarios import build_scenario

_PROGRAM = "openspec"
# The variables a run sets for the tool, which a call keeps of the environment it was given.
_TOOL_ENV_PREFIXES = ("OPENSPEC_", "OPEN_SPEC_", "XDG_CONFIG_HOME", "DO_NOT_TRACK")


@dataclass(frozen=True)
class OpenSpecCall:
    """A command the fake answered: its arguments after the program name, the directory it was
    started from, and the tool's environment variables it was given."""

    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str]


class OpenSpecFake:
    """`shutil.which` and `subprocess.run` for a test whose code starts OpenSpec."""

    def __init__(
        self,
        version: str,
        scenarios: dict[str, dict[tuple[str, ...], RecordedRun]],
        bin_dir: Path,
        committed_skills: Path,
        trees: Path,
    ) -> None:
        self.version = version
        self.scenarios = scenarios
        self.bin_dir = bin_dir
        self.committed_skills = committed_skills
        self.trees = trees
        self.scenario = BASE_SCENARIO
        self.installed = True
        self.calls: list[OpenSpecCall] = []
        self._scripted: dict[tuple[str, ...], RecordedRun | None] = {}
        self._real_run = subprocess.run
        self._real_which = shutil.which

    def tree(self, scenario: str) -> Path:
        """Build the checkout of `scenario` for the test and answer the runs recorded over it."""
        root = self.trees / scenario
        root.mkdir()
        build_scenario(scenario, root, self.committed_skills)
        self.scenario = scenario
        return root

    def script(
        self, arguments: tuple[str, ...], returncode: int, stdout: str = "", stderr: str = ""
    ) -> None:
        """Answer `openspec <arguments>` with this run instead of the recorded one, in any scenario."""
        self._scripted[arguments] = RecordedRun(arguments, returncode, stdout, stderr)

    def hang(self, arguments: tuple[str, ...]) -> None:
        """Make `openspec <arguments>` run past its timeout, as `subprocess.run` reports it."""
        self._scripted[arguments] = None

    def which(self, cmd: Any, mode: int = os.F_OK | os.X_OK, path: Any = None) -> str | None:
        """Where `openspec` is, while installed, else where the host has the program."""
        if Path(os.fsdecode(cmd)).name == _PROGRAM:
            return str(self.bin_dir / _PROGRAM) if self.installed else None
        return self._real_which(cmd, mode, path)

    def _recorded(self, argv: tuple[str, ...]) -> RecordedRun:
        """The run scripted for `argv`, else the one recorded in the selected scenario, else in the
        base scenario."""
        scripted = self._scripted.get(argv)
        if scripted is not None:
            return scripted
        runs = {**self.scenarios[BASE_SCENARIO], **self.scenarios[self.scenario]}
        if argv not in runs:
            pytest.fail(
                f"no run of `openspec {' '.join(argv)}` is recorded for the {self.scenario!r} "
                "scenario: record the real tool again (tests/support/openspec_recording.py)",
                pytrace=False,
            )
        return runs[argv]

    def _update(self, cwd: Path) -> None:
        """What `openspec update --force` leaves under `cwd` with the isolated profile: in each
        agent's tree that already holds a skill of OpenSpec's (or the `.agents` marker), the
        committed skills and no other skill of OpenSpec's. It finds an agent by its skills, so a
        tree that was deleted whole stays deleted (tried: 1.14.3 printed "No configured tools
        found" and wrote nothing)."""
        from devops_cli.openspec.skills import generated_files

        configured = tuple(
            tree
            for tree in (".claude", ".agents")
            if any(
                entry.name.startswith("openspec-") or entry.name == ".openspec-target"
                for entry in (cwd / tree / "skills").glob("*")
            )
        )
        for tree in configured:
            for stale in (cwd / tree / "skills").glob("openspec-*"):
                shutil.rmtree(stale)
        (cwd / ".agents/skills/.openspec-target").unlink(missing_ok=True)
        for path, content in generated_files(self.committed_skills).items():
            if path.startswith(configured):
                (cwd / path).parent.mkdir(parents=True, exist_ok=True)
                (cwd / path).write_bytes(content)

    def run(self, args: Any, *popenargs: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        """Answer an `openspec` command with its recorded run; run any other command for real."""
        argv = [os.fsdecode(arg) for arg in args] if isinstance(args, (list, tuple)) else []
        if not argv or Path(argv[0]).name != _PROGRAM:
            return self._real_run(args, *popenargs, **kwargs)
        cwd = Path(kwargs["cwd"])
        arguments = tuple(argv[1:])
        env = {
            key: value
            for key, value in kwargs.get("env", {}).items()
            if key.startswith(_TOOL_ENV_PREFIXES)
        }
        self.calls.append(OpenSpecCall(arguments, cwd, env))
        if arguments in self._scripted and self._scripted[arguments] is None:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 0))
        recorded = self._recorded(arguments)
        if arguments == ("update", "--force"):
            self._update(cwd)
        as_text = any(kwargs.get(key) for key in ("text", "universal_newlines", "encoding"))
        stdout = recorded.stdout.replace("{cwd}", str(cwd))
        stderr = recorded.stderr.replace("{cwd}", str(cwd))
        return subprocess.CompletedProcess(
            argv,
            recorded.returncode,
            stdout if as_text else stdout.encode(),
            stderr if as_text else stderr.encode(),
        )


@pytest.fixture
def openspec_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> OpenSpecFake:
    """The recorded OpenSpec, found and answered for the whole test."""
    version, scenarios = load_recorded_runs()
    trees = tmp_path / "openspec-trees"
    trees.mkdir()
    fake = OpenSpecFake(
        version,
        scenarios,
        tmp_path / "openspec-bin",
        Path(str(files("tests"))).parent,
        trees,
    )
    monkeypatch.setattr(shutil, "which", fake.which)
    monkeypatch.setattr(subprocess, "run", fake.run)
    return fake
