"""The `Elapsed:` line of a command goes to a terminal only (#5448).

The line comes from an `atexit` hook, which `CliRunner` never runs, so the pipe and the terminal
cases start the CLI as a child process. `PYTHONPATH` names this tree's `src`, so a replay of
`devops ci fail-to-pass --base origin/main` runs the base source rather than the editable install
of the head checkout. The two in-process cases read the hook itself, which the child cases cannot
cover.
"""

from __future__ import annotations

import io
import os
import pty
import subprocess
import sys
from collections.abc import Callable
from typing import Any

import pytest

from tests.support.paths import REPO_ROOT

CHILD_ARGV = [sys.executable, "-P", "-m", "devops_cli.entry", "gh", "--help"]
CHILD_TIMEOUT_SECONDS = 180


def _child_environment(**overrides: str) -> dict[str, str]:
    """The child's environment: this tree's source on `sys.path`, plus `overrides`."""
    return {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), **overrides}


def _run_child(**overrides: str) -> subprocess.CompletedProcess[bytes]:
    """Run the CLI child with stdout and stderr on pipes."""
    return subprocess.run(
        CHILD_ARGV,
        cwd=REPO_ROOT,
        env=_child_environment(**overrides),
        capture_output=True,
        timeout=CHILD_TIMEOUT_SECONDS,
        check=False,
    )


def _open_a_pseudo_terminal() -> tuple[int, io.TextIOWrapper]:
    """Open a pseudo-terminal, and answer its read descriptor and its write stream."""
    try:
        master_fd, slave_fd = pty.openpty()
    except OSError as exc:
        pytest.skip(f"the host has no pseudo-terminal for the test: {exc}")
    return master_fd, os.fdopen(slave_fd, "w", buffering=1)


def _read_chunk(fd: int) -> bytes:
    """Read one chunk of a pseudo-terminal, and nothing once its last slave has closed."""
    try:
        return os.read(fd, 4096)
    except OSError:
        return b""


def _read_to_end(fd: int) -> bytes:
    """Read a pseudo-terminal until the child that held its slave has closed it."""
    chunks: list[bytes] = []
    while chunk := _read_chunk(fd):
        chunks.append(chunk)
    return b"".join(chunks)


def _run_child_with_stderr_on_a_pseudo_terminal() -> bytes:
    """Run the CLI child with stderr on a pseudo-terminal and answer what it wrote there."""
    master_fd, terminal = _open_a_pseudo_terminal()
    try:
        subprocess.run(
            CHILD_ARGV,
            cwd=REPO_ROOT,
            env=_child_environment(),
            stdout=subprocess.DEVNULL,
            stderr=terminal.fileno(),
            timeout=CHILD_TIMEOUT_SECONDS,
            check=False,
        )
    finally:
        terminal.close()
    try:
        return _read_to_end(master_fd)
    finally:
        os.close(master_fd)


@pytest.mark.live("python")
def test_a_pipe_gets_no_elapsed_line() -> None:
    """A command whose stderr is a pipe writes no `Elapsed:` line (#5448)."""
    child = _run_child()
    assert (child.returncode, b"Elapsed:" in child.stderr) == (0, False)


@pytest.mark.live("python")
def test_force_color_with_a_pipe_gets_no_elapsed_line() -> None:
    """`FORCE_COLOR` and `TTY_COMPATIBLE` do not make a pipe a terminal (#5448)."""
    child = _run_child(FORCE_COLOR="1", TTY_COMPATIBLE="1")
    assert (child.returncode, b"Elapsed:" in child.stderr) == (0, False)


@pytest.mark.live("python")
def test_a_pseudo_terminal_gets_the_elapsed_line() -> None:
    """A command whose stderr is a terminal still writes the `Elapsed:` line (#5448)."""
    written = _run_child_with_stderr_on_a_pseudo_terminal()
    assert b"Elapsed:" in written


def test_a_pipe_stream_gets_no_elapsed_line(
    cli: Callable[..., Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """The hook writes no line to a stderr that is a pipe (#5448)."""
    from devops_cli.main import print_elapsed

    cli("gh", "--help")
    print_elapsed()
    assert "Elapsed:" not in capsys.readouterr().err


def test_a_terminal_stream_gets_the_elapsed_line(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook writes the line to a stderr that is a terminal (#5448)."""
    from devops_cli.main import print_elapsed

    cli("gh", "--help")
    original = sys.stderr
    master_fd, terminal = _open_a_pseudo_terminal()
    monkeypatch.setattr(sys, "stderr", terminal)
    print_elapsed()
    monkeypatch.setattr(sys, "stderr", original)
    terminal.close()
    written = _read_to_end(master_fd)
    os.close(master_fd)
    assert b"Elapsed:" in written
