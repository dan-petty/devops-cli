"""The one registry of the tools of every roadmap job and MCP role (#3244).

`TOOLS` names each tool once, with its one-line purpose, its read-only flag and the holders that
name it. These tests read the table, the two functions that serve it, the real MCP role tables and
the real stage toolsets. Each test imports the registry itself, so a tree without the module fails
each test and not the collection of this file. No test reaches a model, the network or a program.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.mcp.roles import JOB_ROLES, named_job_tools
from devops_cli.roadmap.stage.stage_tools import StageTools

_SHA = "0" * 40


def test_each_entry_has_a_one_line_purpose_a_read_only_flag_and_a_holder() -> None:
    from devops_cli.roadmap.tools import HOLDERS, TOOLS

    problems = [
        name
        for name, entry in TOOLS.items()
        if (
            not entry.purpose
            or "\n" in entry.purpose
            or not entry.purpose.endswith(".")
            or not isinstance(entry.read_only, bool)
            or not entry.holders
            or not entry.holders <= set(HOLDERS)
        )
    ]

    assert problems == []


def test_each_holder_names_the_entries_that_hold_it_in_table_order() -> None:
    from devops_cli.roadmap.tools import HOLDERS, TOOLS, tool_names

    held = {holder: list(tool_names(holder)) for holder in HOLDERS}
    expected = {
        holder: [name for name, entry in TOOLS.items() if holder in entry.holders]
        for holder in HOLDERS
    }

    assert held == expected


def test_every_holder_holds_at_least_one_tool() -> None:
    from devops_cli.roadmap.tools import HOLDERS, tool_names

    assert [holder for holder in HOLDERS if not tool_names(holder)] == []


def test_tool_names_refuses_a_holder_that_the_registry_does_not_know() -> None:
    from devops_cli.roadmap.tools import tool_names

    with pytest.raises(ValueError, match="Unknown tool holder 'admin'"):
        tool_names("admin")


def test_check_tables_names_the_table_and_the_tool_that_the_registry_lacks() -> None:
    from devops_cli.roadmap.tools import check_tables

    problems = check_tables({"sample": ["read_file", "no_such_tool"]})

    assert problems == [
        "The table 'sample' names the tool 'no_such_tool', which the registry does not hold."
    ]


def test_check_tables_passes_a_table_of_registry_names() -> None:
    from devops_cli.roadmap.tools import check_tables, tool_names

    assert check_tables({"sample": tool_names("stage")}) == []


def test_the_real_role_tables_name_only_tools_of_the_registry() -> None:
    from devops_cli.roadmap.tools import check_tables, tool_names

    assert check_tables({role: tool_names(role) for role in JOB_ROLES}) == []
    assert check_tables({"job-roles": named_job_tools()}) == []


def test_the_real_stage_toolsets_name_only_tools_of_the_registry(tmp_path: Path) -> None:
    from devops_cli.roadmap.tools import check_tables

    base = StageTools(source=tmp_path, sha=_SHA, toolset="base")
    extended = StageTools(source=tmp_path, sha=_SHA, toolset="extended")

    tables = {
        "stage": [tool.name for tool in base.tools()],
        "stage-extended": [tool.name for tool in extended.tools()],
    }

    assert (check_tables(tables), {len(names) for names in tables.values()}) == ([], {9, 12})
