"""A call whose arguments break the published schema is refused before its handler runs."""

from __future__ import annotations

import pytest

from devops_cli.ai.mcp.server import (
    security_intel_network,
)
from devops_cli.exceptions import ValidationError
from tests.support.fakes.mcp_dispatcher import DispatcherFake
from tests.support.mcp_client import call_tool

_SECRET_SENTINEL = "API_KEY=sentinel-4b1d"


def test_fastmcp_arg_validation() -> None:
    """Verify that a tool catches flag injection attempts."""
    import pytest

    from devops_cli.ai.mcp.server import security_intel_network
    from devops_cli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="must not start with a hyphen"):
        security_intel_network("--all")


def test_a_tool_refuses_a_value_that_starts_with_a_hyphen(mcp_dispatcher: DispatcherFake) -> None:
    """A value with a leading hyphen could pass as a flag, so the tool refuses it."""
    with pytest.raises(ValidationError, match="must not start with a hyphen"):
        security_intel_network("--malicious-flag")

    assert mcp_dispatcher.call_count == 0


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("review_pr", {"number": True, "post": True}),
        ("review_pr", {"number": "1"}),
        ("review_pr", {"number": 1.0}),
        ("review_pr", {"number": 1, "post": "true"}),
        ("sandbox_stop", {"timeout": True}),
        ("sandbox_stop", {"timeout": "10"}),
        ("sandbox_stop", {"timeout": 10.0}),
        ("sandbox_stop", {"all_instances": "true"}),
        ("ai_ast_graph", {"max_files": 2.0}),
    ],
)
async def test_a_coerced_argument_is_refused_before_the_handler_runs(
    tool, arguments, handler_runner
) -> None:
    """`review_pr` given `{"number": true, "post": true}` built `devops review pr 1 --post`.

    Pydantic's lax mode turned `true`, `"1"` and `1.0` into PR 1, so a malformed or
    hallucinated call reviewed PR 1 and commented on it. `sandbox_stop` is withheld from the
    listing, which is all the SDK's own strict check ever looks at, so it must refuse too.
    An integral float on an integer that is not a PR number, such as `sandbox_stop`'s
    `timeout` or the advertised `ai_ast_graph`'s `max_files`, ran its handler the same way.
    """
    is_error, _ = await call_tool(tool, arguments)
    assert (is_error, handler_runner.call_count) == (True, 0)


@pytest.mark.parametrize(
    ("tool", "arguments", "parameter", "kind"),
    [
        ("review_pr", {}, "number", "MISSING_PARAM"),
        ("review_pr", {"number": 0}, "number", "OUT_OF_RANGE"),
        ("pr_monitor", {"number": 0}, "number", "OUT_OF_RANGE"),
        ("review_pr", {"number": 7, "verbose": True}, "verbose", "HALLUCINATED_PARAM"),
        ("review_pr", {"number": "7"}, "number", "TYPE_MISMATCH"),
        ("review_pr", {"number": 7.0}, "number", "TYPE_MISMATCH"),
        ("roadmap_intake", {"filed_by": "everything"}, "filed_by", "INVALID_CHOICE"),
    ],
)
async def test_each_violation_is_numbered_with_its_parameter_and_kind(
    tool, arguments, parameter, kind, handler_runner
) -> None:
    """The envelope says which parameter broke which rule, one numbered entry each."""
    _, reply = await call_tool(tool, arguments)
    assert f"1. Parameter: `{parameter}`\n   Kind: {kind}\n" in reply


async def test_a_parameter_that_breaks_two_keywords_is_listed_once(handler_runner) -> None:
    """`5` for `roadmap_intake`'s `filed_by` fails its `enum` and its `type`.

    Each failed keyword became an entry with the same expected value and fix, doubling the
    count and taking a second of the five places a violation on another parameter needs.
    """
    _, reply = await call_tool("roadmap_intake", {"filed_by": 5})
    assert (
        "1 argument violation(s)" in reply,
        "1. Parameter: `filed_by`" in reply,
        "2. Parameter" in reply,
    ) == (True, True, False)


async def test_a_refusal_names_the_parameter_its_type_and_the_allowed_parameters(
    handler_runner,
) -> None:
    """A model corrects the call in one turn only when told what to send instead.

    Pydantic's own text stopped at the first breach, quoted the value and listed nothing
    the call could have sent.
    """
    _, reply = await call_tool("review_pr", {"number": "4242", "verbose": True})
    assert (
        "Parameter: `number`" in reply,
        "Expected: integer >= 1" in reply,
        "Parameter: `verbose`" in reply,
        "Allowed parameters:" in reply and "`number`" in reply and "`post_comment`" in reply,
        "Re-issue the call" in reply,
        "4242" in reply,
    ) == (True, True, True, True, True, False)


async def test_a_withheld_tool_refuses_with_the_same_envelope(handler_runner) -> None:
    """Calling a withheld tool still works, so it must be refused the same way."""
    _, reply = await call_tool("sandbox_stop", {"timeout": "10"})
    assert (
        "Parameter: `timeout`" in reply,
        "Expected: integer" in reply,
        "Allowed parameters: `all_instances`, `dry_run`, `instance_id`, `timeout`" in reply,
    ) == (True, True, True)


async def test_a_strict_refusal_is_rendered_like_a_schema_refusal(
    handler_runner, fastmcp_log
) -> None:
    """The strict PR-number alias still refuses `1.0` when the schema check lets it through.

    Pydantic reports that refusal. FastMCP logs the refusal's error count and types, and logs
    the call's arguments at DEBUG. The reply goes through the same envelope, and neither it nor
    any FastMCP record holds the value.
    """
    from unittest.mock import patch

    with patch("devops_cli.ai.mcp.server.schema_violations", return_value=[]):
        is_error, reply = await call_tool("review_pr", {"number": 4242.0})
    assert (
        is_error,
        "Kind: TYPE_MISMATCH" in reply,
        "Allowed parameters:" in reply,
        "4242" in reply,
        "Invalid arguments for tool" in fastmcp_log.text,
        "4242" in fastmcp_log.text,
        handler_runner.call_count,
    ) == (True, True, True, False, True, False, 0)


async def test_a_refused_secret_never_reaches_the_reply(handler_runner) -> None:
    """An invalid call returned the secret it was given in its error text."""
    _, reply = await call_tool("valkey_set", {"key": ["bad"], "value": _SECRET_SENTINEL})
    assert ("Parameter: `key`" in reply, "sentinel-4b1d" in reply) == (True, False)


async def test_an_undeclared_parameter_name_is_masked_and_bounded(handler_runner) -> None:
    """An undeclared name is the caller's text, so it is masked and cut before it is echoed."""
    token = "ghp_A1b2C3d4E5f6G7h8I9j0"
    _, reply = await call_tool("review_pr", {"number": 7, token: 1, "x" * 500: 1})
    assert ("Kind: HALLUCINATED_PARAM" in reply, token in reply, "x" * 65 in reply) == (
        True,
        False,
        False,
    )


def test_no_rejected_input_reaches_a_log_record(fastmcp_log, handler_runner) -> None:
    """FastMCP logs a refused call's pydantic error count and types, never the input.

    This holds FastMCP to that. It calls past the middleware, as FastMCP itself does once
    middleware has run, so pydantic refuses a malformed `valkey_set` and FastMCP logs.
    """
    import asyncio

    from fastmcp.exceptions import ValidationError as FastMCPValidationError

    from devops_cli.ai.mcp.server import mcp

    arguments = {"key": ["bad"], "value": _SECRET_SENTINEL}
    with pytest.raises(FastMCPValidationError) as raised:
        asyncio.run(mcp.call_tool("valkey_set", arguments, run_middleware=False))
    assert raised.value is not None
    assert (
        "Invalid arguments for tool" in fastmcp_log.text,
        "sentinel-4b1d" in fastmcp_log.text,
    ) == (True, False)


async def test_no_tool_argument_reaches_a_debug_record(
    fastmcp_log, mcp_dispatcher: DispatcherFake
) -> None:
    """FastMCP logs every tool call's arguments at DEBUG.

    With `FASTMCP_LOG_LEVEL=DEBUG`, that wrote the value of a `valkey_set` call to the log.
    """
    await call_tool("valkey_set", {"key": "session", "value": _SECRET_SENTINEL})
    assert (
        "Handler called: call_tool valkey_set" in fastmcp_log.text,
        "sentinel-4b1d" in fastmcp_log.text,
        mcp_dispatcher.call_count,
    ) == (True, False, 1)


async def test_an_unknown_tool_is_left_to_fastmcp(handler_runner) -> None:
    """The contract checks registered tools; an unknown name keeps FastMCP's own answer."""
    is_error, reply = await call_tool("no_such_tool", {})
    assert (is_error, "Unknown tool" in reply) == (True, True)


async def test_a_validation_error_without_a_pydantic_cause_is_not_rewritten() -> None:
    """Only pydantic's argument errors become an envelope; anything else passes through."""
    from types import SimpleNamespace

    from fastmcp.exceptions import ValidationError as FastMCPValidationError

    from devops_cli.ai.mcp.server import ArgumentContractMiddleware

    async def call_next(_context: object) -> object:
        raise FastMCPValidationError("not an argument error")

    context = SimpleNamespace(message=SimpleNamespace(name="review_pr", arguments={"number": 7}))
    with pytest.raises(FastMCPValidationError, match="not an argument error"):
        await ArgumentContractMiddleware().on_call_tool(context, call_next)


def test_strict_input_validation_stays_off() -> None:
    """The published-schema middleware is the one argument check.

    The SDK's strict check sees only listed tools, quotes the rejected value instead of
    naming the field, and answers before any middleware, so turning it on would leave
    withheld tools coercing and pre-empt the prescriptive envelope on listed ones.
    """
    from devops_cli.ai.mcp.server import mcp

    assert mcp.strict_input_validation is False


def test_fastmcp_k8s_security_stream_validation() -> None:
    from fastmcp.exceptions import ToolError

    from devops_cli.ai.mcp.server import k8s_security_stream

    with pytest.raises(ToolError, match="1<=x<=10000"):
        k8s_security_stream(tail=0)

    with pytest.raises(ToolError, match="Invalid severity"):
        k8s_security_stream(severity="NonExistent")
