"""The security scanners a review starts, faked at the tool executor's seam, and the
`scanner_fake` fixture that installs the fake (#1666, #1982, ADR 0007).

A scanner starts its tool through a `ToolExecutor` (`devops_cli.security.tool_executor`). A
scanner that nobody gives an executor gets a `DirectToolExecutor`. `ScannerFake` is the shared fake
of that seam, `ToolExecutorFake`, scripted with the recorded run of each scanner. It answers a
request for a scanner it holds with the exit code, the standard output and the standard error of
that run, and starts nothing. A test that needs another answer, such as a failed scan, scripts it
with `script`. For the whole test, the fixture makes every `DirectToolExecutor` answer through the
fake, also an executor made before the test, such as that of each scanner of the global registry.
So every scan that gets no executor of its own reaches the fake. A request for any other tool goes
on to the `run` that the fixture replaced: git runs, and the floor of the suite refuses a real
scanner. So does the canary run of a tool, in a working directory named with
`CONST_CANARY_WORKDIR_PREFIX`: the root conftest answers it with the recorded canary output
(`pin_review_tool_canaries`), and the canary of a scanner that the fake holds still passes. The fake records each run as the direct executor does: a checkout that git cannot read
has no commit, and a file that it cannot digest has the digest `unavailable`.

A scanner first looks for its program on PATH. The fake puts a stand-in for each scanner that it
answers in `bin_dir`, and the fixture puts `bin_dir` first on PATH, so `shutil.which` finds the
scanner there. A test that sets PATH without `bin_dir` has no scanner installed. Nothing starts the
stand-in: code that starts a scanner outside the executor reaches the floor, which refuses the
scanner by its name. `runs` holds each request that the fake answered: the command that the direct
executor starts, the directory that it starts the command in and, when the fake snapshots working
directories, the bytes of each file in that directory as the run started.

Each recorded run is the real tool's, at the version `tools.lock` pins, started through its
adapter as a review starts it, over one file holding `print("hello")`, on 2026-10-20: a scan
that finds nothing. Semgrep's was recorded again on 2026-10-22, offline, with a rule file in
place of the registry's `p/default`, which a recording cannot fetch. They are kept in
`tests/fixtures/scanner_runs/recorded_runs.json`, each with its command, in which `{tree}` stands
for the scanned tree, `{workdir}` for the directory the scanner ran in and `{rule_pack}` for
devops-cli's Semgrep rule pack. The contract suite, `tests/test_scanner_contract.py`, starts each
adapter that way over the fake and checks that it still makes the recorded command and reads the
run as it read the real one, and that each recording is of the locked version. When either
changes, record the run again: start the adapter as the contract suite does, with the real tool
at its locked version on PATH, and keep the command, exit code, stdout and stderr it ran with.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.support.fakes.tool_executor import ToolAnswer, ToolExecutorFake

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolRequest, ToolResult

# The stand-in on PATH for a scanner that the fake answers. Nothing runs it.
_STAND_IN = (
    "#!/bin/sh\necho 'scanner_fake answers this scanner through the tool executor' >&2\nexit 127\n"
)


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
    """A command the fake answered, the directory it started in and, when the fake snapshots
    working directories, the bytes of each file in that directory as the run started."""

    argv: list[str]
    cwd: str
    workdir_files: dict[str, bytes] = field(default_factory=dict)


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


class ScannerFake(ToolExecutorFake):
    """The tool executor of a test whose code starts security scanners: each scanner that it
    answers is on PATH under `bin_dir`, and answers with its recorded run or the scripted one."""

    def __init__(self, recorded: dict[str, RecordedScannerRun], bin_dir: Path) -> None:
        super().__init__(require_commit=False, require_files=False)
        self.recorded = recorded
        self.bin_dir = bin_dir
        self.programs: set[str] = set()
        self.runs: list[ScannerRun] = []
        self.snapshot_workdirs = False
        bin_dir.mkdir(parents=True, exist_ok=True)
        for program, run in recorded.items():
            self.script(
                program,
                ToolAnswer(
                    exit_code=run.returncode,
                    stdout=run.stdout,
                    stderr=run.stderr,
                    version=run.version,
                ),
            )

    def script(self, tool: str, answer: ToolAnswer) -> None:
        """Answer every later request for `tool` with `answer`, and put a stand-in for `tool` in
        `bin_dir`, so that the scanner finds its program."""
        super().script(tool, answer)
        stand_in = self.bin_dir / tool
        stand_in.write_text(_STAND_IN, encoding="utf-8")
        stand_in.chmod(0o755)
        self.programs.add(tool)

    def _workdir_files(self, cwd: Path) -> dict[str, bytes]:
        """The name and bytes of each file in `cwd`, when the fake snapshots working directories."""
        if not self.snapshot_workdirs:
            return {}
        return {path.name: path.read_bytes() for path in cwd.iterdir() if path.is_file()}

    def run(self, request: ToolRequest) -> ToolResult:
        """Keep the run of `request`, then answer it with the answer of its tool."""
        cwd = request.cwd or request.workdir
        program = str(request.program) if request.program else request.tool
        self.runs.append(
            ScannerRun([program, *request.arguments], str(cwd), self._workdir_files(cwd))
        )
        return super().run(request)


@pytest.fixture
def scanner_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ScannerFake:
    """The recorded security scanners, on PATH and answered for the whole test."""
    from devops_cli.config.constants import CONST_CANARY_WORKDIR_PREFIX
    from devops_cli.security.tool_executor import DirectToolExecutor

    fake = ScannerFake(recorded_scanner_runs(), tmp_path / "scanner-bin")
    monkeypatch.setenv("PATH", os.pathsep.join([str(fake.bin_dir), os.environ.get("PATH", "")]))
    direct_run = DirectToolExecutor.run

    def run(executor: DirectToolExecutor, request: ToolRequest) -> ToolResult:
        is_canary = request.workdir.name.startswith(CONST_CANARY_WORKDIR_PREFIX)
        if request.tool in fake.programs and not is_canary:
            return fake.run(request)
        return direct_run(executor, request)

    # On the class, so that the fake also answers an executor made before the test.
    monkeypatch.setattr(DirectToolExecutor, "run", run)
    return fake
