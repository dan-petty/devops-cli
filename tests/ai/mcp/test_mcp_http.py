"""The streamable HTTP transport of the MCP server: one endpoint for each job role, behind a
bearer token (#3219). The app runs in process, and no test opens a socket."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from devops_cli.ai.mcp.remote import BearerTokenVerifier, build_http_app, resolve_token
from devops_cli.ai.mcp.server import run_mcp_server
from devops_cli.exceptions import SecurityError
from devops_cli.lang import ERRORS

_TOKEN = "t0ken-" + "a" * 40
_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _rpc(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}


def _post(client: TestClient, path: str, body: dict[str, Any], token: str | None = _TOKEN) -> Any:
    headers = dict(_HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(path, headers=headers, json=body)


def _tool_names(client: TestClient, role: str) -> set[str]:
    response = _post(client, f"/{role}/mcp", _rpc("tools/list"))
    return {tool["name"] for tool in response.json()["result"]["tools"]}


pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(build_http_app(_TOKEN)) as test_client:
        yield test_client


def test_each_role_endpoint_lists_the_tools_of_its_role(client: TestClient) -> None:
    planning, implementation, review = (
        _tool_names(client, role) for role in ("planning", "implementation", "review")
    )
    assert (len(planning), len(implementation), len(review)) == (28, 17, 16)
    assert "k8s_pods" in planning
    assert "k8s_pods" not in review


@pytest.mark.parametrize("token", [None, "", "wrong-" + "a" * 40, _TOKEN[:-1], _TOKEN + "x"])
def test_a_request_without_the_token_is_refused_with_401(
    client: TestClient, token: str | None
) -> None:
    response = _post(client, "/planning/mcp", _rpc("tools/list"), token=token)
    assert (response.status_code, response.headers["www-authenticate"].startswith("Bearer")) == (
        401,
        True,
    )


def test_a_call_with_a_wrong_token_runs_no_tool(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    body = _rpc("tools/call", {"name": "k8s_pods", "arguments": {}})
    with caplog.at_level(logging.INFO):
        response = _post(client, "/planning/mcp", body, token="wrong-" + "a" * 40)
    assert (response.status_code, [r for r in caplog.messages if "MCP tool call" in r]) == (401, [])


def test_a_request_with_a_basic_credential_is_refused(client: TestClient) -> None:
    headers = {**_HEADERS, "Authorization": f"Basic {_TOKEN}"}
    response = client.post("/planning/mcp", headers=headers, json=_rpc("tools/list"))
    assert response.status_code == 401


def test_a_mutating_tool_called_by_name_on_a_job_endpoint_is_unknown(client: TestClient) -> None:
    body = _rpc("tools/call", {"name": "gh_issue_create", "arguments": {}})
    result = _post(client, "/planning/mcp", body).json()["result"]
    assert (result["isError"], result["content"][0]["text"]) == (
        True,
        "Unknown tool: 'gh_issue_create'",
    )


def test_a_tool_call_is_logged_with_its_role_and_no_argument(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    # `number` is a string, so the argument contract refuses the call before the tool runs.
    body = _rpc("tools/call", {"name": "pr_diff", "arguments": {"number": "1", "repo": "o/secret"}})
    with caplog.at_level(logging.INFO):
        _post(client, "/review/mcp", body)
    assert [r for r in caplog.messages if "MCP tool call" in r] == [
        "MCP tool call: role=review tool=pr_diff"
    ]


@pytest.mark.parametrize("path", ["/ops/mcp", "/mcp", "/", "/planning", "/planning/sse"])
def test_a_path_that_is_no_job_endpoint_gives_404_even_with_the_token(
    client: TestClient, path: str
) -> None:
    assert _post(client, path, _rpc("tools/list")).status_code == 404


def test_the_app_serves_no_documentation_page(client: TestClient) -> None:
    assert [client.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")] == [
        404,
        404,
        404,
    ]


def test_the_verifier_accepts_only_the_exact_token() -> None:
    import asyncio

    verifier = BearerTokenVerifier(_TOKEN)
    accepted = asyncio.run(verifier.verify_token(_TOKEN))
    refused = [
        asyncio.run(verifier.verify_token(candidate))
        for candidate in ("", _TOKEN[:-1], _TOKEN.upper(), _TOKEN + " ", "x" * len(_TOKEN))
    ]
    assert (accepted is not None and accepted.client_id, refused) == (
        "mcp-gateway",
        [None] * 5,
    )


@pytest.mark.parametrize("token", ["", "   ", "short"])
def test_the_verifier_refuses_to_exist_without_a_usable_token(token: str) -> None:
    with pytest.raises(SecurityError, match="Refusing to start the streamable-http transport"):
        BearerTokenVerifier(token)


def test_the_remote_transport_refuses_to_start_without_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_MCP_TOKEN", raising=False)
    with pytest.raises(SecurityError) as refused:
        run_mcp_server(transport="streamable-http")
    assert str(refused.value) == ERRORS.mcp.token_required


def test_the_remote_transport_refuses_a_short_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_TOKEN", "short")
    with pytest.raises(SecurityError) as refused:
        run_mcp_server(transport="streamable-http")
    assert str(refused.value) == ERRORS.mcp.token_too_short.format(minimum=32)


def test_the_remote_transport_refuses_a_non_loopback_host_without_allow_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_TOKEN", _TOKEN)
    with pytest.raises(SecurityError, match="Refusing to bind streamable HTTP transport"):
        run_mcp_server(transport="streamable-http", host="192.0.2.10")


def test_the_token_comes_from_the_mcp_token_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MCP_TOKEN", f"  {_TOKEN}\n")
    assert resolve_token() == _TOKEN
