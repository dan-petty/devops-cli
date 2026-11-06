"""The committed skill that calls the scaffold commands (#3204): each agent root holds it, it
names both commands, and the roots hold the same text. An agent reads only the skills of its own
root, so a skill in one root reaches one agent."""

from __future__ import annotations

import pytest

from tests.support.paths import REPO_ROOT

SKILL_ROOTS = (".claude/skills", ".agents/skills")
SCAFFOLD_SKILL = "new-scaffold/SKILL.md"
SCAFFOLD_COMMANDS = ("devops new command", "devops new test")


@pytest.mark.parametrize("root", SKILL_ROOTS)
def test_the_scaffold_skill_of_each_root_names_both_commands(root: str) -> None:
    """The skill of the root names `devops new command` and `devops new test`."""
    text = (REPO_ROOT / root / SCAFFOLD_SKILL).read_text(encoding="utf-8")

    assert [command in text for command in SCAFFOLD_COMMANDS] == [True, True]


def test_the_scaffold_skill_holds_the_same_text_in_each_root() -> None:
    """One text, so no agent reads an older copy."""
    texts = {
        (REPO_ROOT / root / SCAFFOLD_SKILL).read_text(encoding="utf-8") for root in SKILL_ROOTS
    }

    assert len(texts) == 1
