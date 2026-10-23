"""The shipped tuicr files: a config template for the person and the files that tuicr hides.

tuicr reads no project config, so a person copies the template to `~/.config/tuicr/config.toml`
once. The template must keep the update check off (tuicr calls crates.io at start) and must give
every comment type a definition, because the export legend shows the definition to the agent.
"""

from __future__ import annotations

import tomllib
from typing import Any

from devops_cli.config.constants import CONST_DOCS_CLASS_GENERATED, CONST_DOCS_INVENTORY
from tests.support.paths import REPO_ROOT

_TEMPLATE = REPO_ROOT / ".devops" / "tuicr.config.toml"
_IGNORE_FILE = REPO_ROOT / ".tuicrignore"


def _template() -> dict[str, Any]:
    return tomllib.loads(_TEMPLATE.read_text(encoding="utf-8"))


def test_the_template_keeps_the_update_check_off() -> None:
    """tuicr makes one request to crates.io at start unless `no_update_check` is true."""
    assert _template()["no_update_check"] is True


def test_every_comment_type_of_the_template_has_a_definition_for_the_legend() -> None:
    """The legend tells the agent what each type asks for, and SDLC.md names these three ids."""
    types = _template()["comment_types"]

    assert [entry["id"] for entry in types] == ["issue", "question", "nit"]
    assert [entry["id"] for entry in types if not entry.get("definition")] == []


def test_the_ignore_file_hides_only_generated_documents() -> None:
    """A lockfile, the tools lock and CHANGELOG.md stay in front of the person."""
    patterns = [
        line
        for line in _IGNORE_FILE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]

    assert patterns != []
    assert set(patterns) <= set(CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_GENERATED])
