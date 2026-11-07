"""The one registry of the tools of the roadmap jobs and the MCP role servers (#3244).

Each test imports the registry inside itself, so that a checkout without the module fails every
test of this file on its own, in its call phase, and the group proves a failing test on the base.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.mcp.roles import JOB_ROLES, named_job_tools
from devops_cli.roadmap.stage.stage_tools import StageTools

_STAGE_TOOLS = (
    "list_files",
    "read_file",
    "search_code",
    "git_log",
    "git_show",
    "file_symbols",
    "callers",
    "repo_map",
    "read_spec",
)
_STAGE_EXTENDED_TOOLS = ("references", "read_issue", "find_issues")
_IMPLEMENT_TOOLS = frozenset(
    {"read_file", "write_file", "edit_file", "list_files", "grep", "shell"}
)


def test_every_entry_holds_a_name_a_purpose_a_flag_and_a_holder() -> None:
    from devops_cli.roadmap.tools import HOLDERS, TOOLS

    entries = list(TOOLS)

    assert entries
    for entry in entries:
        assert entry.name
        assert entry.purpose.strip()
        assert "\n" not in entry.purpose
        assert isinstance(entry.read_only, bool)
        assert entry.holders
        assert entry.holders <= set(HOLDERS)


def test_each_name_appears_once_with_one_purpose() -> None:
    from devops_cli.roadmap.tools import TOOLS

    names = [entry.name for entry in TOOLS]

    assert len(names) == len(set(names))


def test_tool_names_gives_the_stage_tools_in_table_order() -> None:
    from devops_cli.roadmap.tools import tool_names

    assert tool_names("stage") == _STAGE_TOOLS
    assert tool_names("stage-extended") == _STAGE_EXTENDED_TOOLS


def test_tool_names_gives_the_six_tools_of_the_implement_step() -> None:
    from devops_cli.roadmap.tools import tool_names

    assert set(tool_names("implement")) == _IMPLEMENT_TOOLS


def test_every_holder_names_at_least_one_tool() -> None:
    from devops_cli.roadmap.tools import HOLDERS, tool_names

    assert [holder for holder in HOLDERS if not tool_names(holder)] == []


def test_tool_names_refuses_a_holder_that_the_table_does_not_know() -> None:
    from devops_cli.roadmap.tools import tool_names

    with pytest.raises(ValueError, match="holds no holder 'docker'"):
        tool_names("docker")


def test_check_tables_names_a_table_and_its_missing_tool() -> None:
    from devops_cli.roadmap.tools import check_tables

    problems = check_tables(
        {"planning": ["gh_issues_list", "gh_issue_list"], "stage": ["read_file"]}
    )

    assert problems == [
        "The table planning names the tool gh_issue_list, which the registry does not hold."
    ]


def test_check_tables_finds_no_problem_in_a_table_of_the_registry() -> None:
    from devops_cli.roadmap.tools import check_tables, tool_names

    assert check_tables({"stage": tool_names("stage")}) == []


def test_the_real_role_tables_hold_no_name_outside_the_registry() -> None:
    from devops_cli.roadmap.tools import check_tables

    assert check_tables({"job roles": named_job_tools()}) == []


def test_the_real_stage_toolset_holds_no_name_outside_the_registry(tmp_path: Path) -> None:
    from devops_cli.roadmap.tools import check_tables

    sha = "0" * 40
    toolsets = {
        toolset: StageTools(source=tmp_path, sha=sha, toolset=toolset)
        for toolset in ("base", "extended")
    }

    assert (
        check_tables(
            {toolset: [tool.name for tool in tools.tools()] for toolset, tools in toolsets.items()}
        )
        == []
    )


@pytest.mark.parametrize("role", JOB_ROLES)
def test_every_tool_of_a_role_table_only_reads(role: str) -> None:
    from devops_cli.roadmap.tools import TOOLS, tool_names

    entries = {entry.name: entry for entry in TOOLS}

    assert [name for name in tool_names(role) if not entries[name].read_only] == []
