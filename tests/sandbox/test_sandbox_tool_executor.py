"""The sandbox executor checks the host one time, then runs each tool with what the tool needs
(#2096).

These cases fake the process edge with `process_fake`, so no sandbox and no tool starts. The
executor gets a `HostSandbox` with a stand-in for bubblewrap that nothing starts.
`tests/test_tool_executor_contract.py` runs the real sandbox.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_TOOL_HOST_READ_ONLY_PATHS,
    CONST_TOOL_MIN_ADDRESS_SPACE_BYTES,
)
from devops_cli.exceptions.sandbox import SandboxUnavailableError
from devops_cli.sandbox.host import HostSandbox
from devops_cli.security.tool_executor import SandboxToolExecutor, ToolLimits, ToolRequest
from tests.support.fakes.process import ProcessAnswer, ProcessFake

_NAMESPACE_REFUSED = "bwrap: setting up uid map: Permission denied"
_GIB = 1024**3


@pytest.fixture
def bwrap(tmp_path: Path) -> Path:
    """A stand-in for bubblewrap. Nothing starts it: `process_fake` answers it."""
    stand_in = tmp_path / "bin" / "bwrap"
    stand_in.parent.mkdir()
    stand_in.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    stand_in.chmod(0o755)
    return stand_in


@pytest.fixture
def sandbox_scan_tree(tmp_path: Path) -> Path:
    """A tree outside any checkout, with one file to scan."""
    root = (tmp_path / "tree").resolve()
    root.mkdir()
    (root / "app.py").write_text('print("hello")\n', encoding="utf-8")
    return root


def _request(tree: Path, tool: str = "gitleaks", **fields: Any) -> ToolRequest:
    """A request to run `tool` over the one file of `tree`."""
    return ToolRequest(
        tool=tool,
        arguments=("dir", "{targets}"),
        workdir=tree,
        targets=(tree / "app.py",),
        **fields,
    )


def _binds(command: list[str]) -> list[list[str]]:
    """Each bind option of a sandbox command, as `[flag, source, destination]`."""
    options = command[: command.index("--")]
    return [options[i : i + 3] for i, flag in enumerate(options) if flag in {"--ro-bind", "--bind"}]


def _installed(monkeypatch: pytest.MonkeyPatch, programs: dict[str, Path | None]) -> None:
    """Make `shutil.which` find each of `programs` at its path, or find none."""
    which = shutil.which

    def find(name: str, *args: Any, **kwargs: Any) -> str | None:
        if name in programs:
            path = programs[name]
            return None if path is None else str(path)
        return which(name, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", find)


def _stand_in(tmp_path: Path, tool: str) -> Path:
    """A native program file for `tool`, so that a test does not depend on the tools of the host."""
    program = tmp_path / "stand-ins" / tool
    program.parent.mkdir(exist_ok=True)
    program.write_text("", encoding="utf-8")
    return program


def test_the_executor_checks_the_host_one_time_then_starts_each_tool_in_the_sandbox(
    sandbox_scan_tree: Path, bwrap: Path, process_fake: ProcessFake
) -> None:
    """The check starts `prlimit -- true` in a sandbox. Each run then starts bubblewrap, with
    `prlimit` and the tool in it, under the limits of the request."""
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    executor.run(_request(sandbox_scan_tree))
    executor.run(_request(sandbox_scan_tree))

    probe, first, second = (call.argv for call in process_fake.calls)
    prlimit = shutil.which("prlimit")
    assert (
        (probe[0], probe[probe.index("--") + 1 :]),
        (first[0], first[first.index("--") + 1 :]),
        first == second,
        executor.refusal,
    ) == (
        (str(bwrap), (prlimit, "--", "true")),
        (
            str(bwrap),
            (
                prlimit,
                "--cpu=600",
                f"--as={CONST_TOOL_MIN_ADDRESS_SPACE_BYTES}",
                "--",
                shutil.which("gitleaks"),
                "dir",
                str(sandbox_scan_tree / "app.py"),
            ),
        ),
        True,
        None,
    )


@pytest.mark.parametrize("case", ["no bubblewrap", "no prlimit", "no user namespace"])
def test_a_host_that_cannot_start_the_sandbox_runs_no_tool_and_names_the_cause(
    case: str,
    sandbox_scan_tree: Path,
    bwrap: Path,
    tmp_path: Path,
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The executor refuses each run with the cause, and starts nothing but the check. It checks
    the host one time, so a second run starts nothing more."""
    binary = tmp_path / "missing" / "bwrap" if case == "no bubblewrap" else bwrap
    if case == "no prlimit":
        _installed(monkeypatch, {"prlimit": None})
    process_fake.answer(str(bwrap), ProcessAnswer(returncode=1, stderr=f"{_NAMESPACE_REFUSED}\n"))
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=binary))
    causes = {
        "no bubblewrap": f"bubblewrap ({binary}) is not installed",
        "no prlimit": "prlimit (util-linux) is not installed",
        "no user namespace": f"bubblewrap cannot make a sandbox on this host: {_NAMESPACE_REFUSED}",
    }

    refusals = []
    for _ in range(2):
        with pytest.raises(SandboxUnavailableError) as refused:
            executor.run(_request(sandbox_scan_tree))
        refusals.append(refused.value.message)

    assert (refusals, executor.refusal, len(process_fake.calls)) == (
        [causes[case]] * 2,
        causes[case],
        1 if case == "no user namespace" else 0,
    )


def test_the_sandbox_binds_the_program_of_a_tool_read_only(
    sandbox_scan_tree: Path, bwrap: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sandbox shows only the system directories and the tree, so it binds the program that
    starts the tool. A native program is one file. A program in the `bin` of a virtualenv needs
    the virtualenv, which holds its interpreter link and its packages."""
    native = tmp_path / "tools" / "trivy"
    native.parent.mkdir()
    native.write_text("", encoding="utf-8")
    venv = tmp_path / "semgrep-env"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    (venv / "bin" / "semgrep").write_text("", encoding="utf-8")
    _installed(monkeypatch, {"trivy": native, "semgrep": venv / "bin" / "semgrep"})
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    trivy = _binds(executor.command(_request(sandbox_scan_tree, "trivy")))
    semgrep = _binds(executor.command(_request(sandbox_scan_tree, "semgrep")))

    assert (
        ["--ro-bind", str(native), str(native)] in trivy,
        ["--ro-bind", str(venv), str(venv)] in semgrep,
    ) == (True, True)


def test_the_sandbox_binds_the_paths_of_the_host_that_a_tool_reads_when_it_starts(
    sandbox_scan_tree: Path, bwrap: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The engine of Semgrep loads the CA bundle when it starts, though a scan uses no network,
    and stops without it. The sandbox shows no `/etc`, so it binds what the tool reads there."""
    _installed(monkeypatch, {tool: _stand_in(tmp_path, tool) for tool in ("semgrep", "gitleaks")})
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))
    needed = [
        ["--ro-bind", path, path]
        for path in CONST_TOOL_HOST_READ_ONLY_PATHS["semgrep"]
        if Path(path).exists()
    ]

    semgrep = _binds(executor.command(_request(sandbox_scan_tree, "semgrep")))
    gitleaks = _binds(executor.command(_request(sandbox_scan_tree, "gitleaks")))

    assert ([bind for bind in needed if bind in semgrep], [b for b in needed if b in gitleaks]) == (
        needed,
        [],
    )


def test_the_sandbox_binds_each_writable_directory_of_a_request_read_write(
    sandbox_scan_tree: Path, bwrap: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool that keeps a cache, as mypy does, writes it in a directory that the request names.
    It is the one place outside the private HOME where the tool writes."""
    cache = tmp_path / "cache" / "mypy"
    cache.mkdir(parents=True)
    _installed(monkeypatch, {"mypy": _stand_in(tmp_path, "mypy")})
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=bwrap))

    command = executor.command(_request(sandbox_scan_tree, "mypy", writable_dirs=(cache,)))

    assert _binds(command)[-1] == ["--bind", str(cache), str(cache)]


@pytest.mark.parametrize(
    ("tool", "address_space"),
    [
        ("gitleaks", 8 * _GIB),
        ("semgrep", 16 * _GIB),
        ("bandit", CONST_TOOL_MIN_ADDRESS_SPACE_BYTES),
    ],
)
def test_each_tool_gets_the_address_space_it_was_measured_to_need(
    tool: str, address_space: int
) -> None:
    """Gitleaks runs RE2 as WebAssembly, and Semgrep reserves memory for each of its jobs. Both
    reserve more address space than the least that a tool gets."""
    limits = ToolLimits.for_tool(tool, wall_seconds=9.0)

    assert (limits.address_space_bytes, limits.wall_seconds) == (address_space, 9.0)
