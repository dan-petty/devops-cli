"""A read-only MCP tool publishes no option that writes (#3235).

A role server and a client choose tools by the `readOnlyHint` of the exposure table. A tool that
the table marks read-only but that has an option to resolve, write, delete or create would give
a model a write that the flag says it cannot make. The help text of an option is the signal: the
generator copies it into the description of the published parameter.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Callable, Sequence
from typing import Annotated

import pytest
from fastmcp import FastMCP
from fastmcp.tools import Tool
from pydantic import Field

from devops_cli.ai.mcp.generator import resolve_click_command
from devops_cli.ai.mcp.server import mcp

# The write verbs of the issue, in the forms that say what an option does: the base form, the
# `-s` form and the `-ing` form. A past form ("resolved via 'extends'") describes a result, not a
# write, so it does not match.
_WRITE_STEMS = ("resolv", "writ", "delet", "creat")
_WRITE_WORD = re.compile(r"\b(?:" + "|".join(_WRITE_STEMS) + r")(?:e|es|ing)\b", re.IGNORECASE)


def _read_only(tool: Tool) -> bool | None:
    return tool.annotations.read_only_hint if tool.annotations else None


def _write_options(tools: Sequence[Tool]) -> list[str]:
    """Every `tool.option` of a read-only tool whose description holds a write verb."""
    found: list[str] = []
    for tool in tools:
        if _read_only(tool) is not True:
            continue
        for option, schema in (tool.parameters or {}).get("properties", {}).items():
            if _WRITE_WORD.search(str(schema.get("description", ""))):
                found.append(f"{tool.name}.{option}")
    return sorted(found)


def _tool_with_option(description: str) -> Callable[..., str]:
    """A tool whose one option has `description`, signed as the generator signs its tools."""

    def tool_fn(*, option: bool = False) -> str:
        return "ok"

    annotation = Annotated[bool, Field(description=description)]
    parameter = inspect.Parameter(
        "option", inspect.Parameter.KEYWORD_ONLY, default=False, annotation=annotation
    )
    setattr(tool_fn, "__signature__", inspect.Signature([parameter], return_annotation=str))
    setattr(tool_fn, "__annotations__", {"option": annotation, "return": str})
    return tool_fn


def _catalogue(*, read_only: bool, description: str) -> Sequence[Tool]:
    """The tools of a server that holds one tool with one option."""
    server = FastMCP("write-option-test")
    server.tool(name="probe", annotations={"readOnlyHint": read_only})(
        _tool_with_option(description)
    )
    return asyncio.run(server._list_tools())


def _published(name: str) -> Tool:
    tool = asyncio.run(mcp.get_tool(name))
    assert tool is not None, f"The server publishes no tool named {name}."
    return tool


def _flags(path: tuple[str, ...]) -> set[str]:
    return {opt for param in resolve_click_command(path).params for opt in param.opts}


def test_a_read_only_tool_with_an_option_that_resolves_is_reported() -> None:
    tools = _catalogue(read_only=True, description="Automatically resolve review threads.")

    assert _write_options(tools) == ["probe.option"]


def test_each_write_verb_in_each_form_is_reported() -> None:
    forms = [
        f"{prefix} {stem}{suffix} the thing."
        for stem in _WRITE_STEMS
        for suffix in ("e", "es", "ing")
        for prefix in ("It", "Skip")
    ]

    reported = [
        text
        for text in forms
        if _write_options(_catalogue(read_only=True, description=text)) == ["probe.option"]
    ]

    assert reported == forms


def test_a_write_verb_in_the_case_of_a_title_is_reported() -> None:
    tools = _catalogue(read_only=True, description="Write findings to this path.")

    assert _write_options(tools) == ["probe.option"]


def test_a_tool_that_is_not_read_only_may_have_a_write_option() -> None:
    tools = _catalogue(read_only=False, description="Automatically resolve review threads.")

    assert _write_options(tools) == []


def test_a_past_form_of_a_write_verb_is_not_reported() -> None:
    tools = _catalogue(read_only=True, description="Inherited policies are resolved via 'extends'.")

    assert _write_options(tools) == []


def test_a_word_that_only_holds_a_write_verb_is_not_reported() -> None:
    tools = _catalogue(read_only=True, description="Filter by the creator or the rewriter.")

    assert _write_options(tools) == []


def test_no_read_only_tool_publishes_a_write_option() -> None:
    """The check runs on the published schema of every tool that the server registers."""
    tools = asyncio.run(mcp._list_tools())

    assert _write_options(tools) == []


@pytest.mark.parametrize(
    ("tool_name", "option"),
    [
        ("pr_check_readiness", "auto_resolve"),
        ("roadmap_refine", "confirm"),
        ("tf_plan", "out"),
    ],
)
def test_a_tool_that_keeps_a_writing_option_is_not_read_only(tool_name: str, option: str) -> None:
    """The tool keeps the option that writes, so its flag says that it writes."""
    tool = _published(tool_name)

    assert _read_only(tool) is False
    assert option in tool.parameters["properties"]


def test_the_readiness_command_keeps_its_auto_resolve_option() -> None:
    assert "--auto-resolve" in _flags(("pr", "check-readiness"))


def test_the_injection_scan_stays_read_only_and_publishes_no_sarif_option() -> None:
    """The scan prints its findings, so its tool leaves out the option that writes a file."""
    tool = _published("scan_injection")

    assert _read_only(tool) is True
    assert "sarif" not in tool.parameters["properties"]
    assert "--sarif" in _flags(("scan", "injection"))
