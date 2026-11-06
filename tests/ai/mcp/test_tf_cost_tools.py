"""Tests for the Terraform cost tool and resource of the MCP server.

The tool hands one `devops` command line to the dispatcher. `mcp_dispatcher` records it, so the
resource test reads the command that the resource sent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.mcp.server import get_tf_cost_latest_resource, tf_cost_breakdown
from tests.support.fakes.mcp_dispatcher import DispatcherFake


def test_tf_cost_breakdown_tool_returns_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify FastMCP tool tf_cost_breakdown produces valid JSON output."""
    monkeypatch.chdir(tmp_path)

    out = tf_cost_breakdown(directory=".", mock=True)

    assert "total_monthly_cost" in out


def test_tf_cost_latest_resource_asks_for_a_mock_breakdown(mcp_dispatcher: DispatcherFake) -> None:
    """Verify FastMCP resource get_tf_cost_latest_resource executes expected command."""
    mcp_dispatcher.answer('{"total_monthly_cost": 108.0}', command=["tf", "cost", "breakdown"])

    out = get_tf_cost_latest_resource()

    assert "108.0" in out
    assert (mcp_dispatcher.last.sub_args, mcp_dispatcher.last.timeout) == (
        ("tf", "cost", "breakdown", ".", "--mock", "--json"),
        30.0,
    )
