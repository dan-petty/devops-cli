"""The security scanners a review starts, faked at the process edge, and the `scanner_fake`
fixture that installs the fake (#1666, ADR 0007).

The process edge has no seam yet (#775), so the fake doubles the stdlib objects themselves, the
fallback `docs/TESTING.md` allows for a stdlib edge: `shutil.which` finds each scanner the fake
holds a recorded run of, under `bin_dir`, and `subprocess.run`, through which `run_subprocess`
starts every scanner, answers a command that starts one with that run's exit code, stdout and
stderr, starting nothing. Every other command is found and run for real, under the suite's
refusal of a real gh or scanner. `runs` holds each command the fake answered, with the
directory it was started from.

Each recorded run is the real tool's, at the version `tools.lock` pins, started through its
adapter as a review starts it, over one file holding `print("hello")`, on 2026-10-20: a scan
that finds nothing. They are kept in `tests/fixtures/scanner_runs/recorded_runs.json`, each with
its command, in which `{tree}` stands for the scanned tree, `{workdir}` for the directory the
scanner ran in and `{rule_pack}` for devops-cli's Semgrep rule pack. The contract suite,
`tests/test_scanner_contract.py`, starts each adapter that way over the fake and checks that it
still makes the recorded command and reads the run as it read the real one, and that each
recording is of the locked version. When either changes, record the run again: start the
adapter as the contract suite does, with the real tool at its locked version on PATH, and keep
the command, exit code, stdout and stderr it ran with.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest


@dataclass(frozen=True)
class RecordedScannerRun:
    """One run of a real scanner: its version, its command, and what it answered."""

    version: str
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ScannerRun:
    """A command the fake answered, and the directory it was started from."""

    argv: list[str]
    cwd: str | None


def recorded_scanner_runs() -> dict[str, RecordedScannerRun]:
    """The recorded runs, by the name of the scanner's program.

    They are read through the `tests` package, as the root conftest reads its recordings, since
    a module that defines a fixture does not import `tests.support.paths`.
    """
    recorded = files("tests").joinpath("fixtures", "scanner_runs", "recorded_runs.json")
    runs: dict[str, dict[str, Any]] = json.loads(recorded.read_text(encoding="utf-8"))
    return {
        program: RecordedScannerRun(
            version=run["version"],
            argv=tuple(run["argv"]),
            returncode=run["returncode"],
            stdout=run["stdout"],
            stderr=run["stderr"],
        )
        for program, run in runs.items()
    }


class ScannerFake:
    """`shutil.which` and `subprocess.run` for a test whose code starts security scanners: each
    recorded scanner is found under `bin_dir` and answers with its recorded run, and every other
    program is found and run for real."""

    def __init__(self, recorded: dict[str, RecordedScannerRun], bin_dir: Path) -> None:
        self.recorded = recorded
        self.bin_dir = bin_dir
        self.runs: list[ScannerRun] = []
        self._real_run = subprocess.run
        self._real_which = shutil.which

    def which(self, cmd: Any, mode: int = os.F_OK | os.X_OK, path: Any = None) -> str | None:
        """Where a recorded scanner is, else where the host has the program."""
        program = Path(os.fsdecode(cmd)).name
        if program in self.recorded:
            return str(self.bin_dir / program)
        return self._real_which(cmd, mode, path)

    def run(self, args: Any, *popenargs: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        """Answer a recorded scanner's command with its recorded run; run any other for real."""
        argv = [os.fsdecode(arg) for arg in args] if isinstance(args, (list, tuple)) else []
        recorded = self.recorded.get(Path(argv[0]).name) if argv else None
        if recorded is None:
            return self._real_run(args, *popenargs, **kwargs)
        cwd = kwargs.get("cwd")
        self.runs.append(ScannerRun(argv, None if cwd is None else os.fsdecode(cwd)))
        as_text = any(kwargs.get(key) for key in ("text", "universal_newlines", "encoding"))
        stdout, stderr = recorded.stdout, recorded.stderr
        answered = subprocess.CompletedProcess(
            argv,
            recorded.returncode,
            stdout if as_text else stdout.encode(),
            stderr if as_text else stderr.encode(),
        )
        if kwargs.get("check"):
            answered.check_returncode()
        return answered


@pytest.fixture
def scanner_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ScannerFake:
    """The recorded security scanners, found and answered for the whole test."""
    fake = ScannerFake(recorded_scanner_runs(), tmp_path / "scanner-bin")
    monkeypatch.setattr(shutil, "which", fake.which)
    monkeypatch.setattr(subprocess, "run", fake.run)
    return fake
