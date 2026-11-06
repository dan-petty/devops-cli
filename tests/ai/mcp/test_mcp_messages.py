"""The server takes its tool descriptions and errors from the localized message catalog."""

from __future__ import annotations


def test_fastmcp_messages_and_errors_localization() -> None:
    """Verify localized error and message catalog integration for FastMCP."""
    from unittest.mock import AsyncMock, patch

    import pytest

    from devops_cli.ai.mcp.server import list_mcp_tools, run_mcp_server, security_intel_network
    from devops_cli.exceptions import SecurityError, ValidationError
    from devops_cli.lang import ERRORS, MESSAGES

    # 1. Fallback tool description uses localized catalog string
    dummy_tool = AsyncMock()
    dummy_tool.name = "sample_tool"
    dummy_tool.description = None
    with patch("devops_cli.ai.mcp.server.mcp._list_tools", return_value=[dummy_tool]):
        tools = list_mcp_tools()
        assert tools[0].description == MESSAGES.mcp.no_description_provided

    # 2. Argument validation error uses localized catalog template
    with pytest.raises(ValidationError) as exc_info:
        security_intel_network("--flag")
    assert ERRORS.mcp.hyphen_prefixed_argument.format(name="target") in str(exc_info.value)

    # 3. Security error for non-loopback host uses localized catalog template
    with pytest.raises(SecurityError) as sec_info:
        run_mcp_server(transport="sse", host="192.168.1.50")
    assert ERRORS.mcp.security_non_loopback.format(transport="SSE", host="192.168.1.50") in str(
        sec_info.value
    )
