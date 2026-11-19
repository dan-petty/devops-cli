"""Offline timeout chain test for roadmap consolidate (#4856)."""

from __future__ import annotations

import pytest

from devops_cli.config.constants import (
    CONST_MCP_ROADMAP_CONSOLIDATE_TIMEOUT_SECONDS,
    CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS,
    CONST_ROADMAP_CONSOLIDATE_RUN_BUDGET_SECONDS,
)
from devops_cli.roadmap.consolidate import check_consolidate_timeout_chain


def test_consolidate_timeout_chain_is_strictly_nested() -> None:
    """The configured limits form a strict chain: request < run budget < tool limit."""
    assert (
        CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS
        < CONST_ROADMAP_CONSOLIDATE_RUN_BUDGET_SECONDS
        < CONST_MCP_ROADMAP_CONSOLIDATE_TIMEOUT_SECONDS
    )
    check_consolidate_timeout_chain(
        CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS,
        CONST_ROADMAP_CONSOLIDATE_RUN_BUDGET_SECONDS,
        CONST_MCP_ROADMAP_CONSOLIDATE_TIMEOUT_SECONDS,
    )


def test_broken_timeout_chain_fails_and_names_limits() -> None:
    """When request timeout >= run budget or run budget >= tool limit, the check fails."""
    with pytest.raises(AssertionError) as exc_info1:
        check_consolidate_timeout_chain(780.0, 780.0, 900.0)
    assert "request timeout" in str(exc_info1.value)
    assert "run budget" in str(exc_info1.value)

    with pytest.raises(AssertionError) as exc_info2:
        check_consolidate_timeout_chain(300.0, 900.0, 900.0)
    assert "run budget" in str(exc_info2.value)
    assert "tool limit" in str(exc_info2.value)


async def test_roadmap_consolidate_tool_schema_publishes_limit_maximum_20() -> None:
    """The roadmap_consolidate MCP tool publishes maximum: 20 for limit (#4856)."""
    from tests.support.mcp_client import published_schemas

    schemas = await published_schemas()
    limit_schema = schemas["roadmap_consolidate"]["properties"]["limit"]
    branches = limit_schema.get("anyOf", [limit_schema])
    int_branches = [b for b in branches if b.get("type") == "integer"]
    assert len(int_branches) == 1
    assert int_branches[0].get("maximum") == 20
    assert int_branches[0].get("minimum") == 1
