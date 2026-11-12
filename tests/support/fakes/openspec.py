"""The OpenSpec the gate starts, faked at the process edge, and the `openspec_fake` fixture that
installs the fake (#1844, ADR 0007).

The process edge has no seam yet (#775), so the fake doubles the stdlib objects themselves:
`shutil.which` finds `openspec` under `bin_dir` while the fake is installed, and `subprocess.run`,
through which `run_subprocess` starts every program, answers an `openspec` command from the record
of the real tool, starting nothing. Every other command, git among them,
is found and run for real, under the suite's refusal of every program but git and bwrap.

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
hand-made `openspec-archive-change`). It moves the folder of a change that a recorded `archive`
run archives, to the folder that run names, as the real tool does (#4270); a scripted `archive`
moves nothing unless the test gives it an `effect`. It answers `list --specs --json` from the tree,
as the real tool does, unless a test scripts it (#4622): the stage job lists the base specs of
each checkout that it plans, and a record of one tree cannot answer for another.
`calls` holds every command the fake answered, with the
directory and the OpenSpec environment it was started with.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
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
# What a successful `openspec archive` prints, with the name of the folder it moved the change to.
_ARCHIVED_AS = re.compile(r"archived as '(?P<folder>[^']+)'")
# The listing of the capabilities, which the fake answers from the tree.
LIST_SPECS = ("list", "--specs", "--json")


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
        self._sequences: dict[tuple[str, ...], list[RecordedRun]] = {}
        self._effects: dict[tuple[str, ...], Callable[[Path], None]] = {}
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
        self,
        arguments: tuple[str, ...],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        effect: Callable[[Path], None] | None = None,
    ) -> None:
        """Answer `openspec <arguments>` with this run instead of the recorded one, in any scenario.
        `effect` changes the files under the directory of the run, as the real tool would."""
        self._scripted[arguments] = RecordedRun(arguments, returncode, stdout, stderr)
        if effect is not None:
            self._effects[arguments] = effect

    def script_sequence(self, arguments: tuple[str, ...], *runs: tuple[int, str]) -> None:
        """Answer `openspec <arguments>` with these runs (exit code, standard output) in order, the
        last one again for each later call, for a command whose answer changes between calls."""
        self._sequences[arguments] = [RecordedRun(arguments, code, out, "") for code, out in runs]

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
        sequence = self._sequences.get(argv)
        if sequence:
            return sequence.pop(0) if len(sequence) > 1 else sequence[0]
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
            for tree in (".claude", ".agents", ".kilocode")
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

    def _archive(self, cwd: Path, change: str, recorded: RecordedRun) -> None:
        """Move the folder of `change` to the folder a successful recorded run names."""
        archived = _ARCHIVED_AS.search(recorded.stdout)
        if recorded.returncode == 0 and archived is not None:
            destination = cwd / "openspec/changes/archive" / archived["folder"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            (cwd / "openspec/changes" / change).rename(destination)

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
        if len(arguments) == 3 and arguments[:2] == ("new", "change"):
            change_dir = cwd / "openspec/changes" / arguments[2]
            change_dir.mkdir(parents=True, exist_ok=True)
            (change_dir / ".openspec.yaml").write_text(
                "schema: spec-driven\ncreated: 2026-11-08\n", encoding="utf-8"
            )
            as_text = any(kwargs.get(key) for key in ("text", "universal_newlines", "encoding"))
            return subprocess.CompletedProcess(
                argv, 0, "" if as_text else b"", "" if as_text else b""
            )
        recorded = (
            RecordedRun(arguments, 0, spec_listing(cwd), "")
            if arguments == LIST_SPECS
            and arguments not in self._scripted
            and arguments not in self._sequences
            else self._recorded(arguments)
        )
        if arguments == ("update", "--force"):
            self._update(cwd)
        if arguments in self._effects:
            self._effects[arguments](cwd)
        elif arguments[:1] == ("archive",) and arguments not in self._scripted:
            self._archive(cwd, arguments[1], recorded)
        as_text = any(kwargs.get(key) for key in ("text", "universal_newlines", "encoding"))
        stdout = recorded.stdout.replace("{cwd}", str(cwd))
        stderr = recorded.stderr.replace("{cwd}", str(cwd))
        return subprocess.CompletedProcess(
            argv,
            recorded.returncode,
            stdout if as_text else stdout.encode(),
            stderr if as_text else stderr.encode(),
        )


def spec_listing(cwd: Path) -> str:
    """What `openspec list --specs --json` prints over `cwd`, trimmed to the ids: each `spec.md`
    under `openspec/specs/`, below a folder and outside a dot folder, as the capability of its
    folder path, flat or nested, sorted by that path (`dist/utils/spec-discovery.js` of 1.14.3).
    The live contract test compares it with the real tool."""
    root = cwd / "openspec" / "specs"
    found = (path.parent.relative_to(root) for path in root.rglob("spec.md"))
    ids = sorted(
        folder.as_posix()
        for folder in found
        if folder.parts and not any(part.startswith(".") for part in folder.parts)
    )
    return json.dumps({"specs": [{"id": capability} for capability in ids]})


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
