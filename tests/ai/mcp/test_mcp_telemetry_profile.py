"""`telemetry_profile` names a trace and runs no command (#980)."""

from __future__ import annotations

from tests.support.fakes.mcp_dispatcher import DispatcherFake
from tests.support.mcp_client import call_tool, published_schemas

_PROFILED_TRACE = "0af7651916cd43dd8448eb211c80319c"


async def test_telemetry_profile_publishes_a_trace_id_and_no_command() -> None:
    """`telemetry_profile(command=...)` ran whatever program an MCP caller named.

    `devops telemetry profile` split the string with `shlex` and ran it with the user's whole
    environment, so a prompt-injected agent ran anything with every credential in reach. An
    MCP caller now names a trace already in Tempo, and the trace ID is all it can send.
    """
    import inspect

    from devops_cli.ai.mcp.server import telemetry_profile

    schema = (await published_schemas())["telemetry_profile"]
    assert (
        tuple(inspect.signature(telemetry_profile).parameters),
        sorted(schema["properties"]),
        schema.get("required"),
    ) == (("trace_id",), ["trace_id"], ["trace_id"])


async def test_telemetry_profile_refuses_a_command_before_anything_runs(handler_runner) -> None:
    """The call that profiled `bash -c true` is refused as a parameter the tool never had."""
    is_error, reply = await call_tool(
        "telemetry_profile", {"command": "bash -c true", "trace_id": _PROFILED_TRACE}
    )
    assert (
        is_error,
        "Parameter: `command`" in reply,
        "HALLUCINATED_PARAM" in reply,
        handler_runner.call_count,
    ) == (True, True, True, 0)


def test_telemetry_profile_reads_the_named_trace(mcp_dispatcher: DispatcherFake) -> None:
    from devops_cli.ai.mcp.server import telemetry_profile

    telemetry_profile(trace_id=_PROFILED_TRACE)
    assert list(mcp_dispatcher.last.argv) == [
        "uv",
        "run",
        "devops",
        "telemetry",
        "profile",
        "--trace-id",
        _PROFILED_TRACE,
    ]
