"""A tool returns the output of its command, or raises a tool error with the status and the output."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from devops_cli.ai.mcp.server import (
    ci,
    review_branch,
    review_findings,
    review_path,
    review_pr,
    review_stats,
)
from tests.support.fakes.mcp_dispatcher import DispatcherFake


def test_a_tool_whose_command_exceeds_its_timeout_reports_the_timeout_without_secrets(
    mcp_dispatcher: DispatcherFake,
) -> None:
    """The timeout text names the command and its timeout. Secrets in the text stay masked."""
    mcp_dispatcher.time_out()

    with pytest.raises(ToolError) as exc_info:
        review_path(["ghp_secrettoken1234567890abcdefghijklmn"], "*.py")

    message = str(exc_info.value)
    assert (
        "Command exited with status 124" in message,
        "timed out after" in message,
        "ghp_secrettoken" not in message,
    ) == (True, True, True)


def test_a_tool_whose_command_fails_raises_a_tool_error_with_the_status_and_the_output(
    mcp_dispatcher: DispatcherFake,
) -> None:
    mcp_dispatcher.answer("error details", exit_code=2)

    with pytest.raises(ToolError) as exc_info:
        review_stats()

    assert (
        "Command exited with status 2" in str(exc_info.value),
        "error details" in str(exc_info.value),
    ) == (
        True,
        True,
    )


def test_the_review_tools_return_the_output_of_their_commands(
    mcp_dispatcher: DispatcherFake,
) -> None:
    mcp_dispatcher.answer("Review Output")

    results = (
        review_path(["src"], "*.py"),
        review_branch("feat/new", "main"),
        review_pr(42, post_comment=True),
        review_findings("20260826-session", status_filter="verified"),
        review_stats(),
    )

    assert (results, mcp_dispatcher.call_count) == (("Review Output",) * 5, 5)


def test_mcp_command_failure_contract_raises_tool_error(mcp_dispatcher: DispatcherFake) -> None:
    """A failing CLI command in-process returns output with error exit code and raises ToolError (#839)."""
    mcp_dispatcher.answer("Unknown option: --nonexistent", exit_code=2)

    with pytest.raises(ToolError) as exc_info:
        ci(check=True)

    err_msg = str(exc_info.value)
    assert (
        "Command exited with status 2" in err_msg,
        "Unknown option: --nonexistent" in err_msg,
    ) == (True, True)
