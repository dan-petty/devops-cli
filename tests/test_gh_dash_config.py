"""The shipped gh-dash config: gh-dash ignores a key it does not know, so a typo changes nothing.

The schema in `tests/fixtures/gh_dash_schema/` is the one gh-dash publishes at
https://gh-dash.dev/schema.json for the pinned version, unchanged (MIT, see its LICENSE.txt). It
lets an object hold any key, so the checks below forbid unknown keys in every object. They also
add the keys the v4.26.2 parser reads and the schema lacks.
"""

from __future__ import annotations

import json
import re
import shlex
from copy import deepcopy
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from devops_cli.core.command_resolver import ArgvPlaceholder, resolve_devops_argv
from devops_cli.tools_lock import load_tools_lock
from tests.support.paths import FIXTURES, REPO_ROOT

_SCHEMA_DIR = FIXTURES / "gh_dash_schema"
_BASE_URI = "https://example.com/gh-dash/"
_BOARD_TEMPLATE = REPO_ROOT / ".github" / "project-template.json"
_SHIPPED_CONFIG = REPO_ROOT / ".gh-dash.yml"

# Keys of internal/config/parser.go (v4.26.2) that the published schema leaves out. This covers
# only the keys the shipped config uses. The parser reads more, for example the top-level key
# `repo` and the keybinding groups `universal`, `branches` and `notifications`.
_SCHEMA_GAPS: dict[str, Any] = {
    "schema.json": {
        "notificationsSections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "filters"],
                "properties": {
                    "title": {"type": "string"},
                    "filters": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1},
                },
            },
        },
        "includeReadNotifications": {"type": "boolean"},
    },
    "schema/defaults.json": {"notificationsLimit": {"type": "integer", "minimum": 1}},
}
# The cells that gh-dash v4.26.2 draws as a Nerd Font glyph (internal/tui/constants/constants.go)
# and that its schema lets a config hide, for each view.
_GLYPH_CELLS = {
    "prs": ("authorIcon", "state", "reviewStatus", "ci"),
    "issues": ("creatorIcon", "state"),
}
# The only template values a key binding may use: the number of a PR or an issue and the name of
# the repository. A branch name, an author or a title can hold shell syntax, and gh-dash puts a
# template value into the shell string without quotes.
_SAFE_TEMPLATE_FIELDS = frozenset({"RepoName", "PrNumber", "IssueNumber"})
_TEMPLATE_VALUE = re.compile(r"\{\{[^}]*\}\}")
_SAFE_TEMPLATE_VALUE = re.compile(r"\{\{\s*\.(\w+)\s*\}\}")
_SHELL_STEPS = frozenset({"|", ";"})


def _forbid_unknown_keys(node: Any) -> None:
    """Set `additionalProperties: false` on every schema that lists its properties."""
    if isinstance(node, dict):
        if "properties" in node:
            node["additionalProperties"] = False
        for child in node.values():
            _forbid_unknown_keys(child)
    elif isinstance(node, list):
        for child in node:
            _forbid_unknown_keys(child)


def _strict_validator() -> Draft202012Validator:
    """The published schema with the gaps filled and unknown keys forbidden.

    The files drop their `$id`: upstream ids do not follow the file paths, so a `$ref` would
    resolve to a path that does not exist. Each file is found by its path under `_BASE_URI`.
    """
    resources = []
    for path in sorted(_SCHEMA_DIR.rglob("*.json")):
        name = path.relative_to(_SCHEMA_DIR).as_posix()
        contents = json.loads(path.read_text(encoding="utf-8"))
        contents.pop("$id", None)
        for key, schema in _SCHEMA_GAPS.get(name, {}).items():
            contents["properties"][key] = deepcopy(schema)
        _forbid_unknown_keys(contents)
        resources.append((_BASE_URI + name, DRAFT202012.create_resource(contents)))
    registry: Registry[Any] = Registry().with_resources(resources)
    return Draft202012Validator({"$ref": _BASE_URI + "schema.json"}, registry=registry)


def _schema_errors(config: dict[str, Any]) -> list[str]:
    """The place and the message of each way `config` breaks the strict schema."""
    return sorted(
        f"{'/'.join(map(str, error.absolute_path))}: {error.message}"
        for error in _strict_validator().iter_errors(config)
    )


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


def test_the_shipped_config_breaks_no_rule_of_the_strict_schema() -> None:
    """Every key of `.gh-dash.yml` is one gh-dash reads, with a value of the right type."""
    assert _schema_errors(_shipped_config()) == []


@pytest.mark.parametrize(
    ("change", "reported"),
    [
        ({"prsSections": []}, "'prsSections' was unexpected"),
        ({"defaults": {"refetchInterval": 15}}, "'refetchInterval' was unexpected"),
        ({"keybindings": {"prs": [{"key": "w", "commmand": "true"}]}}, "'commmand' was unexpected"),
        ({"issuesSections": [{"title": "No filter"}]}, "'filters' is a required property"),
    ],
)
def test_the_strict_schema_refuses_a_misspelt_or_missing_key(
    change: dict[str, Any], reported: str
) -> None:
    """Negative control: a defect in each kind of object is reported, so a pass means something."""
    errors = _schema_errors({**_shipped_config(), **change})

    assert [error for error in errors if reported in error] != []


def test_the_vendored_schema_is_the_schema_of_the_pinned_gh_dash() -> None:
    """A bump of the pin in tools.lock also replaces the vendored schema."""
    vendored = (_SCHEMA_DIR / "VERSION").read_text(encoding="utf-8").strip()

    assert vendored == load_tools_lock().binary["gh-dash"].version


def test_every_pr_section_lists_the_oldest_pull_request_first() -> None:
    """GitHub uses the first `sort:` of a query, so one in the filter wins over gh-dash's own."""
    sorts = [section["filters"] for section in _shipped_config()["prSections"]]

    assert [filters for filters in sorts if "sort:created-asc" not in filters] == []


def test_the_triage_section_filters_like_the_triage_view_of_the_board() -> None:
    """The terminal and the web board show the same issues for triage."""
    views = json.loads(_BOARD_TEMPLATE.read_text(encoding="utf-8"))["views"]
    board_filter = next(
        view["filter"] for view in views if view["name"] == "Triage & Quality Table"
    )
    sections = {
        section["title"]: section["filters"] for section in _shipped_config()["issuesSections"]
    }

    assert sections["Triage and quality"] == board_filter


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


def test_the_shipped_config_refreshes_hourly_and_starts_with_the_preview_closed() -> None:
    """The two values keep gh-dash at about 7 GraphQL points at start and 5 points an hour (#1918).

    The GitHub budget is 5,000 GraphQL points an hour for the token, and AI agents share it. A
    refresh fetches every section of the view on screen: 5 points for the four PR sections. An
    open preview adds 2 points for the selected row at start, at each refresh and at each row a
    person selects. A refresh every 15 minutes with the preview open costs about 28 points an hour.
    """
    defaults = _shipped_config()["defaults"]

    assert (defaults["refetchIntervalMinutes"], defaults["preview"]["open"]) == (60, False)


def test_the_shipped_config_holds_only_ascii() -> None:
    """The file holds only ASCII and sets no glyph.

    gh-dash still draws other icons with Nerd Font glyphs: the preview pane, the notification rows
    and the headers of some columns. A person checks how the terminal shows them.
    """
    assert [line for line in _shipped_config_text().splitlines() if not line.isascii()] == []


def test_the_shipped_config_hides_every_glyph_cell_the_schema_lets_it_hide() -> None:
    """The cells that gh-dash draws as a Nerd Font glyph stay hidden, the author icons included."""
    config = _shipped_config()
    layout = config["defaults"]["layout"]
    shown = [
        f"{view}.{cell}"
        for view, cells in _GLYPH_CELLS.items()
        for cell in cells
        if layout[view].get(cell) != {"hidden": True}
    ]

    assert config["showAuthorIcons"] is False
    assert shown == []
