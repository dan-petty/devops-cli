"""Tests that the MCP tool `ai_benchmark` takes no server URL and no file path from the calling
model (#2638, #2704)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.lang import ERRORS, HELP
from tests.support.fakes.http import WebFake

BENCHMARK_TOOL_PARAMETERS = [
    "models",
    "provider",
    "benchmark_type",
    "tasks_filter",
    "concurrency",
    "format_type",
    "dry_run",
    "explain",
    "samples",
]
"""The parameters that the MCP tool of `devops ai benchmark` publishes: no `servers`, no `output`,
no `document` and no `code`."""

_LOOPBACK_URL = "http://127.0.0.1:8200/v1/sys/seal-status?x="
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


def _graded_chat(request: httpx2.Request) -> httpx2.Response:
    """A canned Ollama chat answer that is a valid peer grade."""
    return httpx2.Response(200, json={"message": {"content": json.dumps(_GRADE)}})


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

    async def test_the_tool_publishes_no_servers_and_no_path_parameter(self) -> None:
        """The schema of the tool holds its own options, no server list and no file path."""
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
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any], web: WebFake
    ) -> None:
        """A call that gives `servers` fails and sends no request.

        On `origin/main` each call dialled `127.0.0.1:8200` and wrote
        `POST /v1/sys/seal-status?x=/api/chat`.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        web.serve(_graded_chat)

        failed, reply = await _call_benchmark_tool(
            {"servers": _LOOPBACK_URL, "models": "qwen3:0.6b"}
        )

        assert (
            failed,
            "1. Parameter: `servers`\n   Kind: HALLUCINATED_PARAM\n" in reply,
            web.sent,
        ) == (True, True, [])

    @pytest.mark.parametrize(
        "models",
        [f"qwen3:0.6b@{_LOOPBACK_URL}", f"qwen3:0.6b, other:1b@{_LOOPBACK_URL}"],
        ids=["one entry", "second entry"],
    )
    async def test_a_model_endpoint_is_refused_and_reaches_no_socket(
        self, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any], models: str, web: WebFake
    ) -> None:
        """A `model@url` entry fails the call and sends no request.

        On `origin/main` each call dialled `127.0.0.1:8200` and wrote
        `POST /v1/sys/seal-status?x=/api/chat`.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        web.serve(_graded_chat)

        failed, reply = await _call_benchmark_tool({"models": models})

        assert (
            failed,
            ERRORS.mcp.model_names_endpoint in reply,
            web.sent,
        ) == (
            True,
            True,
            [],
        )

    @pytest.mark.parametrize("option", ["output", "document", "code"])
    async def test_a_path_argument_is_refused_and_touches_no_file_and_no_socket(
        self,
        config: Callable[..., Any],
        tmp_path: Path,
        option: str,
        web: WebFake,
    ) -> None:
        """A call that gives `output`, `document` or `code` fails before the command runs.

        On `origin/main` the call with `output` wrote a report to that path. The call with
        `document` or `code` read the file and sent its text to the model server.
        """
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        web.serve(_graded_chat)
        target = tmp_path / "target"
        target.mkdir()
        (target / "secret.py").write_text("SECRET_MARKER = 1\n")
        value = str(target / "report.json") if option == "output" else str(target)

        failed, reply = await _call_benchmark_tool(
            {"benchmark_type": "embedding", "models": "m1", option: value}
        )

        assert (
            failed,
            f"1. Parameter: `{option}`\n   Kind: HALLUCINATED_PARAM\n" in reply,
            sorted(path.name for path in target.iterdir()),
            web.sent,
        ) == (True, True, ["secret.py"], [])

    async def test_the_tool_benchmarks_each_model_on_the_configured_server(
        self, config: Callable[..., Any], web: WebFake
    ) -> None:
        """With plain model names, the tool posts its chat requests to the configured server only."""
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.com:11434"]})
        web.serve(_graded_chat)

        failed, _ = await _call_benchmark_tool(
            {"models": "m1,m2", "tasks_filter": "sec-ssrf-remediation"}
        )

        assert (
            failed,
            {f"{request.url.host}:{request.url.port}" for request in web.sent},
            {(request.method, request.url.path) for request in web.sent},
        ) == (False, {"example.com:11434"}, {("POST", "/api/chat")})

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
        web: WebFake,
    ) -> None:
        """Loopback, and private addresses with `ai.allow_private_network`, as for the CLI.

        The floor sets the flag with its environment variable, which outranks the config file, so
        the test sets the variable.
        """
        monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", str(flag).lower())
        config(ai={"provider": "ollama", "ollama_urls": [f"http://{address}:11434"]})
        web.serve(_graded_chat)

        await _call_benchmark_tool({"models": "m1", "tasks_filter": "sec-ssrf-remediation"})

        assert {str(request.url) for request in web.sent} == (
            {f"http://{address}:11434/api/chat"} if dialled else set()
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
        config: Callable[..., Any],
        cli: Callable[..., Any],
        option: str,
        value: str,
        web: WebFake,
    ) -> None:
        """A person types the URL, and no model gives it, so the command posts to that host."""
        config(ai={"provider": "ollama", "ollama_urls": ["http://example.org:11434"]})
        web.serve(_graded_chat)
        arguments = ["ai", "benchmark", "--tasks", "sec-ssrf-remediation", option, value]
        if option == "--servers":
            arguments += ["--models", "m1"]

        result = cli(*arguments)

        assert (
            result.exit_code,
            {f"{request.url.host}:{request.url.port}" for request in web.sent},
        ) == (0, {"example.com:11435"})


@pytest.mark.usefixtures("keyring_store")
class TestBenchmarkToolPublishesPlainModelNames:
    """The `models` description in the schema of `ai_benchmark` names plain models, because the
    tool refuses a `model@url` (#2743)."""

    async def test_the_published_description_gives_an_example_that_the_tool_accepts(self) -> None:
        """The description holds no `model@url` and no key rule, and its example passes the check
        of the tool for a model endpoint.

        On `origin/main` the description quoted `llama3.1:8b@http://gpu2:11434`.
        """
        from fastmcp import Client

        from devops_cli.ai.mcp.generator import _check_model_endpoints
        from devops_cli.ai.mcp.server import mcp

        async with Client(mcp) as client:
            tools = await client.list_tools()
        text = next(t for t in tools if t.name == "ai_benchmark").input_schema["properties"][
            "models"
        ]["description"]
        quoted = re.search(r"'([^']+)'", text)

        assert quoted is not None
        assert [word for word in ("@", "api_base_url", "gateway_url", "key") if word in text] == []
        _check_model_endpoints(("ai", "benchmark"), {"models": quoted.group(1)})

    def test_the_command_help_keeps_the_model_url_form(self) -> None:
        """A person at the command line still reads the `model@url` form."""
        assert "llama3.1:8b@http://gpu2:11434" in HELP.benchmark.models
        assert "The MCP tool refuses a model@url." in HELP.benchmark.models
