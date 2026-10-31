"""The security scanners a review starts, faked at the tool executor's seam, and the
`scanner_fake` fixture that installs the fake (#1666, #1982, ADR 0007).

A scanner starts its tool through a `ToolExecutor` (`devops_cli.security.tool_executor`). A
scanner that nobody gives an executor gets a `DirectToolExecutor`, except Popeye, which gets a
`SandboxToolExecutor` (#2132), and a review that gets no executor runs its tools in a
`SandboxToolExecutor` (#2096). `ScannerFake` is the shared fake of
that seam, `ToolExecutorFake`, scripted with the recorded run of each scanner. It answers a request
for a scanner it holds with the exit code, the standard output and the standard error of that run,
and starts nothing. A test that needs another answer, such as a failed scan, scripts it with
`script`. For the whole test, the fixture makes every `DirectToolExecutor` and every
`SandboxToolExecutor` answer through the fake, also an executor made before the test, such as that
of each scanner of the global registry. So every scan that gets no executor of its own reaches the
fake, and no sandbox starts. A request for any other tool goes on to the `run` that the fixture
replaced: git runs, and the floor of the suite refuses a real scanner and a real sandbox. The fake
records each run as the direct executor does: a checkout that git cannot read has no commit, and a
file that it cannot digest has the digest `unavailable`. It records the network profile of the
request, else `none`, as the sandbox executor does, also for a run that it answers in place of the
direct executor, whose record names `host`.

A review runs the canary of each tool before its scans, in a working directory named with
`CONST_CANARY_WORKDIR_PREFIX`, on the tool executor of the review (#1978). The fake answers each
canary run with the output that the pinned tool printed for its canary, as
`tests/fixtures/review_canary/recorded_outputs.json` holds it, so every canary passes. It keeps the
canary requests apart, in `canaries.requests`, and never in `runs` or `requests`. A test that gives
the review the fake through the constructor of the orchestrator (`tool_executor=scanner_fake`) or
through the fixture's `DirectToolExecutor` gets the same canary answers, and no review starts a
real tool for a canary.

A scanner first looks for its program on PATH. The fake puts a stand-in for each scanner that it
answers in `bin_dir`, and the fixture puts `bin_dir` first on PATH, so `shutil.which` finds the
scanner there. A test that sets PATH without `bin_dir` has no scanner installed. Nothing starts the
stand-in: code that starts a scanner outside the executor reaches the floor, which refuses the
scanner by its name. `runs` holds each request that the fake answered: the command that the direct
executor starts, the directory that it starts the command in and, when the fake snapshots working
directories, the bytes of each file in that directory as the run started.

Each recorded run is the real tool's, at the version `tools.lock` pins, started through its
adapter as a review starts it, over one file holding `print("hello")`, on 2026-10-20: a scan
that finds nothing. Semgrep's was recorded again on 2026-10-28, offline, with a rule file in
place of the registry's `p/default`, which a recording cannot fetch, and with the rules that a
review leaves out (#1024). Gitleaks' was recorded again
on 2026-10-25, with the command that writes its report on stdout (#1434). They are kept in
`tests/fixtures/scanner_runs/recorded_runs.json`, each with its command, in which `{tree}` stands
for the scanned tree, `{workdir}` for the directory the scanner ran in and `{rule_pack}` for
devops-cli's Semgrep rule pack. The contract suite, `tests/test_scanner_contract.py`, starts each
adapter that way over the fake and checks that it still makes the recorded command and reads the
run as it read the real one, and that each recording is of the locked version. When either
changes, record the run again: start the adapter as the contract suite does, with the real tool
at its locked version on PATH, and keep the command, exit code, stdout and stderr it ran with.

A run that finds something is in `tests/fixtures/scanner_runs/runs_with_findings.json`, recorded
on 2026-10-25 with the command each adapter makes, and `script_run_with_findings` answers with it
(#1434). Gitleaks ran over a file that held a GitHub token; its report is redacted, so the token is
not in the recording. Pluto ran over two objects whose APIs Kubernetes removed, one with no
replacement. Popeye ran at warn level over the namespace of a lab cluster; its report keeps three
of its sections and two of its resources, and the names of the cluster and the context read
`example`. uv audit 0.12.23 ran on 2026-10-28 over a project whose `uv.lock` pins idna 3.6
(#2106). No tools lock pins uv, and uv 0.13.6, which the images pin, writes a report of the same
layout. kubeconform ran on 2026-10-28 over a manifest with two invalid resources and one custom
resource with no schema (#2214). tflint 0.65.0 ran on 2026-10-30 with `--format json --recursive`
over a tree of two `.tf` files, one in `modules/network`; it exited 2 with six warnings of its
bundled `terraform` ruleset, and the file name of each issue is relative to the tree (#2427).
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
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


def recorded_canary_answers() -> ToolExecutorFake:
    """A tool executor fake that answers the canary of each review tool with the output that the
    pinned tool printed for it, as `tests/fixtures/review_canary/recorded_outputs.json` holds it.

    The recordings are read through the `tests` package, as `recorded_scanner_runs` reads its own.
    """
    recorded = files("tests").joinpath("fixtures", "review_canary", "recorded_outputs.json")
    entries: dict[str, Any] = json.loads(recorded.read_text(encoding="utf-8"))
    canaries = ToolExecutorFake()
    for tool, entry in entries.items():
        out = entry.get("output", "") if isinstance(entry, dict) else ""
        canaries.script(tool, ToolAnswer(stdout=out if isinstance(out, str) else json.dumps(out)))
    return canaries


def is_canary_run(request: ToolRequest) -> bool:
    """Whether `request` is the canary run of a tool: it starts in a working directory named with
    `CONST_CANARY_WORKDIR_PREFIX`."""
    from devops_cli.config.constants import CONST_CANARY_WORKDIR_PREFIX

    return request.workdir.name.startswith(CONST_CANARY_WORKDIR_PREFIX)


class ScannerFake(ToolExecutorFake):
    """The tool executor of a test whose code starts security scanners: each scanner that it
    answers is on PATH under `bin_dir`, and answers with its recorded run or the scripted one. The
    canary run of every review tool gets the recorded canary answer."""

    def __init__(self, recorded: dict[str, RecordedScannerRun], bin_dir: Path) -> None:
        super().__init__(require_commit=False, require_files=False)
        self.recorded = recorded
        self.bin_dir = bin_dir
        self.programs: set[str] = set()
        self.runs: list[ScannerRun] = []
        self.snapshot_workdirs = False
        self.canaries = recorded_canary_answers()
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

    def script_run_with_findings(self, tool: str, **places: Path) -> ScannerRun:
        """Answer `tool` with its recorded run that finds something, and return the command and
        the directory that run started in.

        The runs are in `tests/fixtures/scanner_runs/runs_with_findings.json`, each the real
        tool's, at the version `tools.lock` pins when it pins one, started with the command its
        adapter makes. In each, a placeholder such as `{tree}` stands for the path given as that
        keyword."""
        recorded = files("tests").joinpath("fixtures", "scanner_runs", "runs_with_findings.json")
        run: dict[str, Any] = json.loads(recorded.read_text(encoding="utf-8"))[tool]

        def placed(text: str) -> str:
            for place, path in places.items():
                text = text.replace(f"{{{place}}}", str(path))
            return text

        self.script(
            tool,
            ToolAnswer(
                exit_code=run["returncode"],
                stdout=placed(run["stdout"]),
                stderr=placed(run["stderr"]),
                version=run["version"],
            ),
        )
        return ScannerRun([placed(word) for word in run["argv"]], placed(run["cwd"]))

    def script(self, tool: str, answer: ToolAnswer) -> None:
        """Answer every later request for `tool` with `answer`, and put a stand-in for `tool` in
        `bin_dir`, so that the scanner finds its program."""
        super().script(tool, answer)
        stand_in = self.bin_dir / tool
        stand_in.write_text(_STAND_IN, encoding="utf-8")
        stand_in.chmod(0o755)
        self.programs.add(tool)

    def answer_with(self, tool: str, responder: Callable[[ToolRequest], ToolAnswer]) -> None:
        """Answer every later request for `tool` with what `responder` gives for the request, and
        put a stand-in for `tool` in `bin_dir`, so that the scanner finds its program."""
        self.script(tool, ToolAnswer())
        super().answer_with(tool, responder)

    def fail(self, tool: str, error: Exception) -> None:
        """Raise `error` from every later request for `tool`, and put a stand-in for `tool` in
        `bin_dir`, so that the scanner finds its program and starts it."""
        self.script(tool, ToolAnswer())
        super().fail(tool, error)

    def _workdir_files(self, cwd: Path) -> dict[str, bytes]:
        """The name and bytes of each file in `cwd`, when the fake snapshots working directories."""
        if not self.snapshot_workdirs:
            return {}
        return {path.name: path.read_bytes() for path in cwd.iterdir() if path.is_file()}

    def run(self, request: ToolRequest) -> ToolResult:
        """Answer a canary run with the recorded canary answer. Keep the run of any other
        `request`, then answer it with the answer of its tool."""
        if is_canary_run(request):
            return self.canaries.run(request)
        cwd = request.cwd or request.workdir
        program = str(request.program) if request.program else request.tool
        self.runs.append(
            ScannerRun([program, *request.arguments], str(cwd), self._workdir_files(cwd))
        )
        return super().run(request)


@pytest.fixture
def scanner_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ScannerFake:
    """The recorded security scanners and tool canaries, on PATH and answered for the whole test."""
    import shutil

    from devops_cli.security.tool_executor import DirectToolExecutor, SandboxToolExecutor

    fake = ScannerFake(recorded_scanner_runs(), tmp_path / "scanner-bin")
    real_git = shutil.which("git")
    if real_git:
        git_target = fake.bin_dir / "git"
        if not git_target.exists():
            git_target.symlink_to(real_git)
    monkeypatch.setenv(
        "PATH", os.pathsep.join([str(fake.bin_dir), str(Path(sys.executable).parent)])
    )
    for executor_class in (DirectToolExecutor, SandboxToolExecutor):
        # On the class, so that the fake also answers an executor made before the test.
        monkeypatch.setattr(executor_class, "run", _answering(fake, executor_class.run))
    return fake


def _answering(
    fake: ScannerFake, replaced: Callable[[Any, ToolRequest], ToolResult]
) -> Callable[[Any, ToolRequest], ToolResult]:
    """A `run` that answers the scanners and the canaries of `fake`, and hands any other request
    to the `run` that it replaces."""

    def run(executor: Any, request: ToolRequest) -> ToolResult:
        if request.tool in fake.programs or is_canary_run(request):
            return fake.run(request)
        return replaced(executor, request)

    return run
