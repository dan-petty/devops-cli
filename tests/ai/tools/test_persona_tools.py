"""Each persona gets its own tool set, and challenger gets read-only tools."""

from __future__ import annotations

import pytest

from devops_cli.ai.personas import Persona
from devops_cli.ai.tools import get_default_tools, get_persona_tools
from devops_cli.ai.tools.builtin_tools import (
    git_diff,
    git_status,
    list_files,
    rag_search,
    read_file,
    search_code,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_each_persona_has_a_tool_set_that_is_not_the_default_set() -> None:
    default = get_default_tools()
    assert [persona for persona in Persona if get_persona_tools(persona) == default] == []


def test_challenger_gets_the_read_only_tools() -> None:
    assert get_persona_tools(Persona.CHALLENGER) == [
        read_file,
        list_files,
        search_code,
        git_diff,
        git_status,
        rag_search,
    ]


def test_a_persona_name_gets_the_tools_of_its_persona() -> None:
    assert get_persona_tools("challenger") == get_persona_tools(Persona.CHALLENGER)
