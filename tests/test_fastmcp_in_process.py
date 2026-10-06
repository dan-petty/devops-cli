"""Unit tests for FastMCP in-process dispatching, lazy schema hydration, and resource subscriptions."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client

from devops_cli.ai.mcp.dispatcher import (
    DomainSchemaHydrator,
    InProcessDispatcher,
    ResourceSubscriptionManager,
    _extract_devops_sub_args,
    get_mcp_dispatcher,
    resolve_tool_domain,
)
from devops_cli.ai.mcp.server import _run_mcp_cmd, _run_mcp_resource, ci_run, mcp
from devops_cli.config.constants import CONST_CI_TEST_BUDGET_SECONDS
from devops_cli.main import app


def test_extract_devops_sub_args() -> None:
    """Verify sub-argument extraction from various command structures."""
    c1 = ["uv", "run", "devops", "config", "show"]
    c2 = ["devops", "repos", "list"]
    c3 = ["git", "status"]
    c4 = ["uv", "pip", "list"]

    assert (_extract_devops_sub_args(c1), _extract_devops_sub_args(c2)) == (
        ["config", "show"],
        ["repos", "list"],
    )
    assert (_extract_devops_sub_args(c3), _extract_devops_sub_args(c4)) == (None, None)


def test_resolve_tool_domain() -> None:
    """Verify prefix-based functional domain resolution."""
    assert (
        resolve_tool_domain("review_path"),
        resolve_tool_domain("k8s_pods"),
        resolve_tool_domain("argo_list"),
        resolve_tool_domain("gh_issue_list"),
        resolve_tool_domain("vault_get"),
        resolve_tool_domain("unknown_cmd"),
    ) == ("review", "k8s", "argo", "github", "secrets", "workspace")


def test_domain_schema_hydrator_cache_and_bounding() -> None:
    """Verify DomainSchemaHydrator caches schemas and evicts at capacity."""
    hydrator = DomainSchemaHydrator(max_cache_entries=2)
    assert hydrator.get_cached_schema("tool1") is None

    hydrator.cache_schema("tool1", {"type": "object", "properties": {"a": {"type": "string"}}})
    hydrator.cache_schema("tool2", {"type": "object", "properties": {"b": {"type": "integer"}}})

    s1 = hydrator.get_cached_schema("tool1")
    s2 = hydrator.get_cached_schema("tool2")
    assert (s1 is not None and "properties" in s1, s2 is not None and "properties" in s2) == (
        True,
        True,
    )

    # Exceed capacity: tool1 should be evicted
    hydrator.cache_schema("tool3", {"type": "object"})
    assert (
        hydrator.get_cached_schema("tool1"),
        hydrator.get_cached_schema("tool3") is not None,
    ) == (
        None,
        True,
    )

    hydrator.clear()
    assert hydrator.get_cached_schema("tool2") is None


def test_resource_subscription_manager() -> None:
    """Verify observer registration, updates, and unsubscriptions for resource:// URIs."""
    manager = ResourceSubscriptionManager()
    events_a: list[tuple[str, str]] = []
    events_b: list[tuple[str, str]] = []

    def listener_a(uri: str, content: str) -> None:
        events_a.append((uri, content))

    def listener_b(uri: str, content: str) -> None:
        events_b.append((uri, content))

    manager.subscribe("resource://config/active", listener_a)
    manager.subscribe("resource://config/active", listener_b)
    manager.subscribe("resource://workspace/status", listener_a)

    assert (
        manager.subscriber_count("resource://config/active"),
        manager.subscriber_count("resource://workspace/status"),
        manager.subscriber_count("resource://nonexistent"),
    ) == (2, 1, 0)

    # Publish notification
    notified_cfg = manager.notify("resource://config/active", "config_data_v1")
    notified_ws = manager.notify("resource://workspace/status", "ws_data_v1")

    assert (notified_cfg, notified_ws) == (2, 1)
    assert (len(events_a), len(events_b)) == (2, 1)
    assert (events_a[0], events_a[1]) == (
        ("resource://config/active", "config_data_v1"),
        ("resource://workspace/status", "ws_data_v1"),
    )

    # Unsubscribe
    manager.unsubscribe("resource://config/active", listener_a)
    assert manager.subscriber_count("resource://config/active") == 1
    manager.unsubscribe("resource://config/active", listener_b)
    assert manager.subscriber_count("resource://config/active") == 0


def test_in_process_dispatcher_functional_handler() -> None:
    """Verify direct Python functional handler registration and invocation."""
    dispatcher = InProcessDispatcher()

    def mock_handler(*args: str) -> tuple[int, str]:
        return 0, f"mocked response with {len(args)} args"

    dispatcher.register_handler(("custom", "action"), mock_handler)
    code, output = dispatcher.dispatch(["uv", "run", "devops", "custom", "action", "arg1", "arg2"])

    assert (code, output) == (0, "mocked response with 2 args")


def test_in_process_dispatcher_typer_dispatch() -> None:
    """Verify in-process execution via Typer CliRunner and execution latency."""
    dispatcher = InProcessDispatcher()

    # Dispatch a known fast command
    start_t = time.perf_counter()
    code, output = dispatcher.dispatch(["devops", "workspace", "-h"])
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    assert (code, "Usage: devops workspace" in output) == (0, True)
    assert elapsed_ms < 10000.0, f"Runaway bound exceeded: {elapsed_ms:.2f}ms >= 10000.0ms"


def test_in_process_dispatcher_subprocess_fallback() -> None:
    """Verify non-devops commands fall back to subprocess execution."""
    dispatcher = InProcessDispatcher()

    mock_proc = MagicMock(returncode=0, stdout="git version 2.40", stderr="")
    with patch("devops_cli.ai.mcp.dispatcher.run_subprocess", return_value=mock_proc) as mock_sub:
        code, output = dispatcher.dispatch(["git", "--version"])
        assert (code, output) == (0, "git version 2.40")
        mock_sub.assert_called_once()


def test_run_mcp_cmd_in_process() -> None:
    """Verify _run_mcp_cmd invokes in-process dispatcher for devops commands."""
    with patch.object(
        InProcessDispatcher,
        "dispatch",
        return_value=(0, "Active Configuration: logfire enabled"),
    ) as mock_disp:
        res = _run_mcp_cmd(["uv", "run", "devops", "config", "show"])
        assert "Active Configuration: logfire enabled" in res
        mock_disp.assert_called_once()


def test_run_mcp_resource_notifications() -> None:
    """Verify _run_mcp_resource queries in-process and notifies resource subscribers."""
    dispatcher = get_mcp_dispatcher()
    received_updates: list[str] = []

    def subscriber(uri: str, content: str) -> None:
        received_updates.append(content)

    test_uri = "resource://test/status"
    dispatcher.subscriptions.subscribe(test_uri, subscriber)

    with patch.object(
        InProcessDispatcher,
        "dispatch",
        return_value=(0, "system ready"),
    ):
        output = _run_mcp_resource(test_uri, ["devops", "test", "status"])
        assert output == "system ready"
        assert len(received_updates) == 1
        assert received_updates[0] == "system ready"

    dispatcher.subscriptions.unsubscribe(test_uri, subscriber)


def test_in_process_dispatch_never_writes_child_output_to_protocol_stream(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A capfd test asserts that nothing reaches the real stdout while a tool dispatches a command whose child prints."""
    cmd_name = "_test_child_stream_839"

    @app.command(name=cmd_name, hidden=True)
    def _test_cmd() -> None:
        os.write(1, b"child direct stdout diagnostic\n")
        os.write(2, b"child direct stderr diagnostic\n")

    try:
        dispatcher = InProcessDispatcher()
        code, out = dispatcher.dispatch(["devops", cmd_name])
        captured = capfd.readouterr()
        assert (
            captured.out,
            code,
            "child direct stdout diagnostic" in out,
            "child direct stderr diagnostic" in out,
        ) == ("", 0, True, True)
    finally:
        app.registered_commands = [c for c in app.registered_commands if c.name != cmd_name]


@pytest.mark.asyncio
async def test_tool_failure_yields_is_error_with_status_and_diagnostic() -> None:
    """A check that exits 1 after printing a diagnostic yields an isError result containing status and diagnostic."""
    async with Client(mcp) as client:
        with patch.object(
            get_mcp_dispatcher(),
            "dispatch",
            return_value=(1, "FAILED tests/test_ci.py::test_gate - Diagnostic details"),
        ):
            res = await client.call_tool("ci_run", {"check": "test"}, raise_on_error=False)
            text = "\n".join(getattr(b, "text", "") for b in res.content)
            assert (
                res.is_error,
                "Command exited with status 1:" in text,
                "FAILED tests/test_ci.py::test_gate - Diagnostic details" in text,
            ) == (True, True, True)


def test_dispatcher_empty_output_fallback_for_success_and_failure() -> None:
    """Exit 0 with empty output returns Success, and non-zero with empty output returns no output captured."""
    dispatcher = InProcessDispatcher()
    with patch.object(dispatcher, "_dispatch_typer", return_value=(0, "")):
        assert dispatcher.dispatch(["devops", "workspace", "list"]) == (0, "Success")

    with patch.object(dispatcher, "_dispatch_typer", return_value=(1, "")):
        assert dispatcher.dispatch(["devops", "workspace", "list"]) == (1, "no output captured")


def test_ci_run_argv_contains_check_and_timeout_exceeds_budget() -> None:
    """The argv ci_run builds contains --check, and its timeout is at least CONST_CI_TEST_BUDGET_SECONDS."""
    all_check_choices = [
        "all",
        "test",
        "lint",
        "format",
        "typecheck",
        "audit",
        "security",
        "actionlint",
        "docs",
        "uv-check",
        "lockfile",
        "outdated",
        "devcontainer",
    ]
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_run:
        mock_run.return_value = "Success"
        for choice in all_check_choices:
            ci_run(check=choice)  # type: ignore[arg-type]
            call_args, call_kwargs = mock_run.call_args
            cmd = call_args[0]
            assert (
                "--check" in cmd,
                call_kwargs["timeout"] >= CONST_CI_TEST_BUDGET_SECONDS,
            ) == (True, True)
