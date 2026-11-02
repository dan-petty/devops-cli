"""`devops mcp serve --transport streamable-http`: the command refuses what the server refuses,
and its dry run lists the bind (#3219)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.lang import ERRORS

pytestmark = pytest.mark.usefixtures("keyring_store")

_TOKEN = "t0ken-" + "a" * 40
_ARGV = ["mcp", "serve", "--transport", "streamable-http"]


def test_serve_refuses_the_remote_transport_without_a_token(
    cli: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_MCP_TOKEN", raising=False)
    result = cli(_ARGV)
    assert (result.exit_code, ERRORS.mcp.token_required in " ".join(result.output.split())) == (
        1,
        True,
    )


def test_serve_dry_run_refuses_the_remote_transport_without_a_token(
    cli: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_MCP_TOKEN", raising=False)
    result = cli([*_ARGV, "--dry-run"])
    assert (result.exit_code, "mcp.token" in result.output) == (1, True)


def test_serve_dry_run_lists_the_bind_and_the_start_of_the_remote_transport(
    cli: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_TOKEN", _TOKEN)
    result = cli([*_ARGV, "--port", "9090", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "BIND tcp 127.0.0.1:9090" in result.output
    assert "START mcp server (streamable-http)" in result.output
    assert _TOKEN not in result.output


def test_serve_refuses_a_remote_host_without_allow_remote(
    cli: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_TOKEN", _TOKEN)
    result = cli([*_ARGV, "--host", "192.0.2.10", "--dry-run"])
    assert (result.exit_code, "Refusing to bind streamable HTTP" in result.output) == (1, True)
