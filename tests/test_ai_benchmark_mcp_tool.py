"""Tests that the MCP tool `ai_benchmark` takes no server URL from the calling model (#2638)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.lang import ERRORS
from tests.web_fakes import PUBLIC_ADDRESS, http_response, record_connects, scripted_resolver

BENCHMARK_TOOL_PARAMETERS = [
    "models",
    "provider",
    "benchmark_type",
    "tasks_filter",
    "concurrency",
    "output",
    "format_type",
    "dry_run",
    "explain",
    "document",
    "code",
    "samples",
]
"""The parameters that the MCP tool of `devops ai benchmark` publishes: no `servers`."""

_LOOPBACK_URL = "http://127.0.0.1:8200/v1/sys/seal-status?x="
_CHAT_REQUEST_LINE = b"POST /api/chat HTTP/1.1"
_GRADE = {
    "accuracy_score": 9.0,
    "security_score": 9.5,
    "completeness_score": 8.0,
    "clarity_score": 9.5,
    "total_score": 36.0,
    "percentage": 90.0,
    "strengths": ["Strong defense"],
    "weaknesses": [],
    "feedback": "Great job",
}


def _chat_answers(count: int = 40) -> list[bytes]:
    """Canned Ollama chat answers, each a valid peer grade."""
    return [http_response(200, json.dumps({"message": {"content": json.dumps(_GRADE)}}))] * count


async def _call_benchmark_tool(arguments: dict[str, object]) -> tuple[bool, str]:
    """Call the tool the way an MCP client does: whether the call failed, and its reply."""
    from fastmcp import Client

    from devops_cli.ai.mcp.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool("ai_benchmark", arguments, raise_on_error=False)
    return bool(result.is_error), "\n".join(getattr(block, "text", "") for block in result.content)


@pytest.mark.usefixtures("keyring_store")
class TestBenchmarkToolTakesNoServerUrlFromTheModel:
    """The MCP tool `ai_benchmark` sends its chat requests to the servers of `ai.ollama_urls`,
    never to a URL that the calling model gives (#2638)."""

    async def test_the_tool_publishes_no_servers_parameter(self) -> None:
        """The schema of the tool holds its own options and no server list."""
        from fastmcp import Client

        from devops_cli.ai.mcp.server import mcp

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert {
            tool.name: list(tool.input_schema["properties"])
            for tool in tools
            if tool.name == "ai_benchmark"
        } == {"ai_benchmark": BENCHMARK_TOOL_PARAMETERS}

    async def test_a_servers_argument_is_refused_and_reaches_no_socket(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
    ) -> None:
        """A call that gives `servers` fails and sends no request.

        On `origin/main` each call dialled `127.0.0.1:8200` and wrote
        `POST /v1/sys/seal-status?x=/api/chat`.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, _chat_answers())

        failed, reply = await _call_benchmark_tool(
            {"servers": _LOOPBACK_URL, "models": "qwen3:0.6b"}
        )

        assert (
            failed,
            "1. Parameter: `servers`\n   Kind: HALLUCINATED_PARAM\n" in reply,
            recorder.dialled,
            recorder.written,
        ) == (True, True, [], [])

    @pytest.mark.parametrize(
        "models",
        [f"qwen3:0.6b@{_LOOPBACK_URL}", f"qwen3:0.6b, other:1b@{_LOOPBACK_URL}"],
        ids=["one entry", "second entry"],
    )
    async def test_a_model_endpoint_is_refused_and_reaches_no_socket(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any], models: str
    ) -> None:
        """A `model@url` entry fails the call and sends no request.

        On `origin/main` each call dialled `127.0.0.1:8200` and wrote
        `POST /v1/sys/seal-status?x=/api/chat`.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, _chat_answers())

        failed, reply = await _call_benchmark_tool({"models": models})

        assert (
            failed,
            ERRORS.mcp.model_names_endpoint in reply,
            recorder.dialled,
            recorder.written,
        ) == (
            True,
            True,
            [],
            [],
        )

    async def test_the_tool_benchmarks_each_model_on_the_configured_server(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
    ) -> None:
        """With plain model names, the tool posts its chat requests to the configured server only."""
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        scripted_resolver(monkeypatch, {"example.com": [[PUBLIC_ADDRESS]]})
        recorder = record_connects(monkeypatch, _chat_answers())

        failed, _ = await _call_benchmark_tool(
            {"models": "m1,m2", "tasks_filter": "sec-ssrf-remediation"}
        )

        assert (
            failed,
            set(recorder.requested_hosts),
            {bytes(written).split(b"\r\n")[0] for written in recorder.written if written},
        ) == (False, {"example.com:11434"}, {_CHAT_REQUEST_LINE})

    @pytest.mark.parametrize(
        ("address", "flag", "dialled"),
        [
            ("127.0.0.1", False, True),
            ("192.0.2.10", False, False),
            ("192.0.2.10", True, True),
        ],
        ids=["loopback without the flag", "private without the flag", "private with the flag"],
    )
    async def test_the_tool_dials_the_configured_server_at_the_configured_level(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config: Callable[..., Any],
        address: str,
        flag: bool,
        dialled: bool,
    ) -> None:
        """Loopback, and private addresses with `ai.allow_private_network`, as for the CLI.

        The floor sets the flag with its environment variable, which outranks the config file, so
        the test sets the variable.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", str(flag).lower())
        config(ai={"provider": "ollama", "ollama_urls": [f"http://{address}:11434"]})
        recorder = record_connects(monkeypatch, _chat_answers())

        await _call_benchmark_tool({"models": "m1", "tasks_filter": "sec-ssrf-remediation"})

        assert {dial for dial in recorder.dialled if dial[0] == address} == (
            {(address, 11434)} if dialled else set()
        )

    @pytest.mark.parametrize(
        ("option", "value"),
        [
            ("--servers", "http://example.com:11435"),
            ("--models", "m1@http://example.com:11435"),
        ],
        ids=["servers", "model endpoint"],
    )
    def test_the_command_runs_on_the_server_that_a_person_types(
        self,
        monkeypatch: pytest.MonkeyPatch,
        config: Callable[..., Any],
        cli: Callable[..., Any],
        option: str,
        value: str,
    ) -> None:
        """A person types the URL, and no model gives it, so the command posts to that host."""
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.org:11434"]})
        scripted_resolver(
            monkeypatch,
            {"example.com": [[PUBLIC_ADDRESS]], "example.org": [[PUBLIC_ADDRESS]]},
        )
        recorder = record_connects(monkeypatch, _chat_answers())
        arguments = ["ai", "benchmark", "--tasks", "sec-ssrf-remediation", option, value]
        if option == "--servers":
            arguments += ["--models", "m1"]

        result = cli(*arguments)

        assert (result.exit_code, set(recorder.requested_hosts)) == (0, {"example.com:11435"})
