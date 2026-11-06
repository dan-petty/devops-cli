"""The server advertises a few domains at first and adds the rest when a client hydrates them."""

from __future__ import annotations


def test_the_advertised_set_is_a_fraction_of_the_registered_one() -> None:
    """All 155 tools were advertised on every turn.

    Their names and summaries alone cost about 2,700 tokens per request before the
    per-parameter JSON Schema the protocol adds, and a model choosing among 155 tools
    chooses worse than one choosing among a few dozen.
    """
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    async def counts() -> tuple[int, int]:
        registered = await mcp_server.mcp._list_tools()
        advertised = [t for t in registered if mcp_server._is_advertised(t.name)]
        return len(registered), len(advertised)

    registered, advertised = asyncio.run(counts())
    assert advertised < registered / 2


def test_filtering_never_removes_a_tool_from_the_server() -> None:
    """An earlier version removed them, which mutated an object every consumer shares.

    The schema exporter, the in-process bridge and every later test then saw whatever the
    last caller had left behind.
    """
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    async def registered_count() -> int:
        return len(await mcp_server.mcp._list_tools())

    before = asyncio.run(registered_count())
    mcp_server.hydrate_tool_domain("k8s")
    mcp_server.reset_hydrated_domains()
    assert asyncio.run(registered_count()) == before


def test_an_eager_domain_needs_no_hydration() -> None:
    """The domains this CLI's agent uses constantly must not cost a round trip first."""
    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.config.constants import CONST_MCP_EAGER_DOMAINS

    eager = sorted(CONST_MCP_EAGER_DOMAINS)[0]
    assert mcp_server._is_advertised(f"{eager}_anything") is True


def test_a_withheld_domain_appears_once_hydrated() -> None:
    """Hydration is the way back; without it the withheld tools are undiscoverable."""
    from devops_cli.ai.mcp import server as mcp_server

    before = mcp_server._is_advertised("k8s_get_pods")
    mcp_server.hydrate_tool_domain("k8s")
    assert (before, mcp_server._is_advertised("k8s_get_pods")) == (False, True)


def test_hydrating_an_eager_domain_is_reported_as_unnecessary() -> None:
    """Asking for something already advertised should not look like it changed anything."""
    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.config.constants import CONST_MCP_EAGER_DOMAINS

    eager = sorted(CONST_MCP_EAGER_DOMAINS)[0]
    assert mcp_server.hydrate_tool_domain(eager)["hydrated"] is False


def test_the_hydration_tool_is_always_advertised() -> None:
    """Withholding it too would make every other withheld domain unreachable."""
    from devops_cli.ai.mcp import server as mcp_server

    assert mcp_server._is_advertised("hydrate_tool_domain") is True


def test_hydrating_invalid_domain_name_is_rejected() -> None:
    """Invalid characters or empty strings are rejected without mutating hydrated domains."""
    from devops_cli.ai.mcp import server as mcp_server

    assert (
        mcp_server.hydrate_tool_domain("")["hydrated"],
        mcp_server.hydrate_tool_domain("; rm -rf /")["hydrated"],
        mcp_server.hydrate_tool_domain("k8s$bad")["hydrated"],
    ) == (False, False, False)


def test_hydrating_unknown_domain_is_rejected() -> None:
    """Nonexistent domains like 'secrets' are rejected with clear explanation."""
    from devops_cli.ai.mcp import server as mcp_server

    res_secrets = mcp_server.hydrate_tool_domain("secrets")
    res_vault = mcp_server.hydrate_tool_domain("vault")
    assert (
        res_secrets["hydrated"],
        res_secrets["detail"],
        res_vault["hydrated"],
    ) == (
        False,
        "unknown domain: secrets",
        True,
    )


def test_hydrate_tool_domain_notifies_session() -> None:
    """Hydrating a domain dispatches notifications/tools/list_changed if session is active."""
    from unittest.mock import AsyncMock, MagicMock

    from devops_cli.ai.mcp import server as mcp_server

    mock_session = MagicMock()
    mock_session.send_tool_list_changed = AsyncMock()
    mock_ctx = MagicMock(session=mock_session)

    res = mcp_server.hydrate_tool_domain("ssh", ctx=mock_ctx)
    assert (res["hydrated"], mock_session.send_tool_list_changed.called) == (True, True)
