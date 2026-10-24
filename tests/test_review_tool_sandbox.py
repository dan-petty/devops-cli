"""A review runs its tools in the network-less sandbox, and in no other place (#2096, decision 1
of #772).

The sandbox is `SandboxToolExecutor`: bubblewrap through `HostSandbox`, with `prlimit` in it.
These cases fake the process edge with `process_fake`, so no sandbox and no tool starts. A
stand-in for bubblewrap first on PATH lets the host check find a bubblewrap binary, and the fake
answers the check and each command. When the fake answers the check with an error of bubblewrap,
the host cannot make a user namespace.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import ReviewClients, _execute_review_workflow
from devops_cli.config.constants import CONST_TOOL_EXECUTOR_SANDBOX
from devops_cli.lang import MESSAGES
from tests.support.fakes.process import ProcessAnswer, ProcessFake

# What bubblewrap prints when the kernel refuses it a user namespace, as AppArmor does on Ubuntu.
_NAMESPACE_REFUSED = "bwrap: setting up uid map: Permission denied"
_CAUSE = f"bubblewrap cannot make a sandbox on this host: {_NAMESPACE_REFUSED}"
_ANALYZERS = ("Bandit", "Gitleaks", "Semgrep")


@pytest.fixture
def bwrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for bubblewrap first on PATH. Nothing starts it: `process_fake` answers it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stand_in = bin_dir / "bwrap"
    stand_in.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(bin_dir), os.environ.get("PATH", "")]))
    return stand_in


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A tree outside any checkout, with one Python file to review."""
    root = (tmp_path / "tree").resolve()
    root.mkdir()
    (root / "app.py").write_text('print("hello")\n', encoding="utf-8")
    return root


def _tool_commands(process_fake: ProcessFake) -> list[tuple[str, ...]]:
    """Each command that the fake answered, less the commands of git."""
    return [call.argv for call in process_fake.calls if Path(call.argv[0]).name != "git"]


def _confined_program(argv: tuple[str, ...]) -> str:
    """The file name of the program that a sandbox command starts. The options of bubblewrap end
    with `--`, and the options of `prlimit` end with the next `--`."""
    under_prlimit = argv[argv.index("--") + 1 :]
    return Path(under_prlimit[under_prlimit.index("--") + 1]).name


def _orchestrator(tree: Path, tmp_path: Path) -> ReviewPipelineOrchestrator:
    """A review of `tree` that gets no executor."""
    return ReviewPipelineOrchestrator(
        session_id="s2096", session_dir=tmp_path / "session", target_dir=tree
    )


def test_a_review_with_no_executor_runs_each_tool_in_the_sandbox(
    tree: Path, tmp_path: Path, bwrap: Path, process_fake: ProcessFake
) -> None:
    """The orchestrator gets no executor, so it starts each analyzer and each canary in the
    sandbox. The host check starts bubblewrap one time. Then each command starts bubblewrap with
    the tool in it, and the record of each run names the sandbox."""
    orchestrator = _orchestrator(tree, tmp_path)

    orchestrator.init_per_file_payloads(["app.py"], {})

    commands = _tool_commands(process_fake)
    probe, *runs = commands
    assert (
        {argv[0] for argv in commands},
        probe[probe.index("--") + 1 :][-1],
        {"bandit", "gitleaks", "semgrep"} <= {_confined_program(argv) for argv in runs},
        {run.executor for run in orchestrator.tool_executor.runs},
    ) == ({str(bwrap)}, "true", True, {CONST_TOOL_EXECUTOR_SANDBOX})


def test_a_review_on_a_host_that_cannot_start_the_sandbox_runs_no_tool_and_reports_a_gap(
    tree: Path, tmp_path: Path, bwrap: Path, process_fake: ProcessFake
) -> None:
    """The host check fails, so no tool starts, in the sandbox or outside it. Each analyzer that
    had files reports a coverage gap that names the cause. No canary ran, so no canary withholds
    a finding."""
    process_fake.answer(str(bwrap), ProcessAnswer(returncode=1, stderr=f"{_NAMESPACE_REFUSED}\n"))
    orchestrator = _orchestrator(tree, tmp_path)

    orchestrator.init_per_file_payloads(["app.py"], {})

    assert (
        len(_tool_commands(process_fake)),
        {name: orchestrator.static_analyzers[name] for name in _ANALYZERS},
        all(_CAUSE in orchestrator.static_analyzer_reasons[name] for name in _ANALYZERS),
        orchestrator.tool_executor.runs,
        orchestrator.canary_results,
    ) == (1, dict.fromkeys(_ANALYZERS, "coverage_gap"), True, (), {})


def test_a_review_that_the_host_cannot_sandbox_says_why_and_what_to_change_on_the_host(
    tree: Path, bwrap: Path, process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    """The review command runs its tools in the sandbox, so on a host that cannot start it, no
    tool runs. The review says one time why, and what a person can change on the host. It offers
    no run outside the sandbox."""
    process_fake.answer(str(bwrap), ProcessAnswer(returncode=1, stderr=f"{_NAMESPACE_REFUSED}\n"))

    _execute_review_workflow(
        [], "app.py", False, ReviewClients(), target_dir=tree, routed_files=["app.py"]
    )

    out = " ".join(capsys.readouterr().out.split())
    message = " ".join(MESSAGES.review.tools_not_sandboxed.format(cause=_CAUSE).split())
    assert (out.count(message), "--no-sandbox" in out, len(_tool_commands(process_fake))) == (
        1,
        False,
        1,
    )
