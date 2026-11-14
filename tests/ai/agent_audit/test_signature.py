"""Tests of the signatures that count one recurring problem across sessions (#2346)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path


def test_paths_and_numbers_are_replaced() -> None:
    """Two runs of one command that differ in a path and in a number have one signature, so the
    audit counts them as one problem (#2346)."""
    from devops_cli.ai.agent_audit.signature import command_signature

    first = command_signature("uv run devops ci test tests/ai/test_a.py -n 3")
    second = command_signature("uv run devops ci test tests/commands/test_b.py -n 7")

    assert first == "uv run devops ci test <path> -n <n>"
    assert second == first


def test_subcommands_flags_and_flag_values_are_kept_apart() -> None:
    """A signature keeps the program, the subcommands and the flags of a command, and replaces
    the value of a flag and the path of a command (#2346)."""
    from devops_cli.ai.agent_audit.signature import command_signature

    assert command_signature("git commit -m one --no-verify") == (
        "git commit -m <value> --no-verify"
    )
    assert command_signature("uv run devops k8s image-pins --format json") == (
        "uv run devops k8s image-pins --format <value>"
    )
    assert command_signature("uv run ruff check --include=src/") == (
        "uv run ruff check --include=<value>"
    )
    assert command_signature("cd src/ && uv run pytest") == "cd <path> && uv run pytest"


def test_a_secret_never_reaches_a_signature() -> None:
    """A secret of a command is masked before the signature leaves the module, so the store, the
    report and the model never hold it (#2346)."""
    from devops_cli.ai.agent_audit.signature import command_signature

    assert command_signature("echo ghp_1234567890abcdefghij") == "echo <masked-github-token>"


def test_a_long_command_is_cut_to_a_bounded_signature() -> None:
    """A command of many words gives a signature of a bounded length, which a stored file and a
    model request can hold (#2346)."""
    from devops_cli.ai.agent_audit.signature import command_signature

    signature = command_signature("devops " + " ".join(["word"] * 40))

    assert signature == "devops " + " ".join(["word"] * 23) + " ..."


def test_error_signature_keeps_the_exit_status() -> None:
    """A failure signature holds the exit status and the normalized first error line, so one
    failure shares a signature across sessions and another status keeps its own (#2346)."""
    from devops_cli.ai.agent_audit.signature import error_signature

    first = error_signature(1, "FAILED tests/ai/test_a.py::test_x - assert 1 == 2")
    second = error_signature(1, "FAILED tests/commands/test_b.py::test_y - assert 3 == 4")

    assert first == "exit 1: failed <path> - assert <n> == <n>"
    assert second == first
    assert error_signature(2, "fatal: not a git repository") == (
        "exit 2: fatal: not a git repository"
    )
    assert error_signature(None, "") == "exit <unknown>"


def test_first_error_line_skips_the_exit_code_line() -> None:
    """The first error line is the first line that is not the line of the exit status (#2346)."""
    from devops_cli.ai.agent_audit.signature import first_error_line

    assert first_error_line("Exit code 1\nFAILED tests/ai/test_x.py::test_y") == (
        "FAILED tests/ai/test_x.py::test_y"
    )
    assert first_error_line("Exit code 1") == ""
    assert first_error_line("") == ""


def test_tool_result_exit_status_extraction() -> None:
    """The exit status of a tool result is the code that its output names, a failed result that
    names none keeps no status, and a result that the tool marks as no error succeeded (#2346)."""
    from devops_cli.ai.agent_audit.signature import tool_result_exit_status

    assert tool_result_exit_status("Exit code 1\nFAILED tests/ai/test_x.py", is_error=True) == 1
    assert tool_result_exit_status("Exit code 127\ncommand not found: rg", is_error=True) == 127
    assert tool_result_exit_status("fatal: not a git repository", is_error=True) is None
    assert tool_result_exit_status("Exit code 0", is_error=False) == 0
    assert tool_result_exit_status("all checks passed", is_error=False) == 0


def test_a_failed_call_holds_its_command_and_its_failure() -> None:
    """The signature of one tool call is its command, and the failure that answered it when the
    call failed (#2346)."""
    from devops_cli.ai.agent_audit.signature import call_signature
    from devops_cli.ai.agent_audit.transcript import ToolCall

    failed = ToolCall(
        session="session-a",
        file=Path("session-a.jsonl"),
        line=2,
        timestamp="2026-01-01T00:00:00.000Z",
        command="uv run devops ci test tests/ai/test_a.py",
        output="Exit code 1\nFAILED tests/ai/test_a.py::test_x",
        is_error=True,
    )

    assert call_signature(failed) == "uv run devops ci test <path> | exit 1: failed <path>"
    assert call_signature(replace(failed, output="Exit code 0", is_error=False)) == (
        "uv run devops ci test <path>"
    )
