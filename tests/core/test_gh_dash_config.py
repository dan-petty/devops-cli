"""The shipped gh-dash config: each key binding runs a `devops` command that exists, and names no
template value that can hold shell syntax (#1882).

The devtools image installs gh-dash, so no copy of its schema is kept here (#4363).
"""

from __future__ import annotations

import re
import shlex
from typing import Any

import yaml

from devops_cli.core.command_resolver import ArgvPlaceholder, resolve_devops_argv
from tests.support.paths import REPO_ROOT

_SHIPPED_CONFIG = REPO_ROOT / ".gh-dash.yml"

# The only template values a key binding may use: the number of a PR or an issue and the name of
# the repository. A branch name, an author or a title can hold shell syntax, and gh-dash puts a
# template value into the shell string without quotes.
_SAFE_TEMPLATE_FIELDS = frozenset({"RepoName", "PrNumber", "IssueNumber"})
_TEMPLATE_VALUE = re.compile(r"\{\{[^}]*\}\}")
_SAFE_TEMPLATE_VALUE = re.compile(r"\{\{\s*\.(\w+)\s*\}\}")
_SHELL_STEPS = frozenset({"|", ";"})


def _shipped_config_text() -> str:
    return _SHIPPED_CONFIG.read_text(encoding="utf-8")


def _shipped_config() -> dict[str, Any]:
    loaded = yaml.safe_load(_shipped_config_text())
    assert isinstance(loaded, dict)
    return loaded


def _bound_commands(config: dict[str, Any]) -> list[str]:
    """The shell command of each key binding in every view."""
    return [
        binding["command"]
        for bindings in config["keybindings"].values()
        for binding in bindings
        if "command" in binding
    ]


def _first_devops_argv(command: str) -> list[ArgvPlaceholder | str]:
    """The tokens after `devops` in the first step of `command`, a template value as a placeholder."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)
    assert tokens[0] == "devops", command
    first_step = tokens[1 : next((i for i, t in enumerate(tokens) if t in _SHELL_STEPS), None)]
    return [
        ArgvPlaceholder(expression=match.group(1), single_token=True)
        if (match := _SAFE_TEMPLATE_VALUE.fullmatch(token))
        else token
        for token in first_step
    ]


def test_a_key_binding_names_no_template_value_that_can_hold_shell_syntax() -> None:
    """gh-dash puts a template value into the shell string without quotes (#1882)."""
    used = {
        match.group(1) if (match := _SAFE_TEMPLATE_VALUE.fullmatch(value)) else value
        for command in _bound_commands(_shipped_config())
        for value in _TEMPLATE_VALUE.findall(command)
    }

    assert used - _SAFE_TEMPLATE_FIELDS == set()


def test_every_key_binding_runs_a_devops_command_that_exists() -> None:
    """The first step of each binding is a `devops` command line the command tree resolves."""
    commands = _bound_commands(_shipped_config())

    assert commands != []
    assert [c for c in commands if resolve_devops_argv(_first_devops_argv(c)) is not None] == []
