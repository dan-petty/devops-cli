"""The committed skills that call the project commands (#3204): each agent root holds them, they
name their commands, and the roots hold the same text. An agent reads only the skills of its own
root, so a skill in one root reaches one agent."""

from __future__ import annotations

import pytest

from tests.support.paths import REPO_ROOT

SKILL_ROOTS = (".claude/skills", ".agents/skills", ".kilocode/skills")
SCAFFOLD_SKILL = "new-scaffold/SKILL.md"
SCAFFOLD_COMMANDS = ("devops new command", "devops new test")
PROJECT_SKILLS: dict[str, tuple[str, ...]] = {
    "new-scaffold/SKILL.md": ("devops new command", "devops new test"),
    "devops-openspec-new/SKILL.md": ("devops openspec new",),
    "devops-pr-ci/SKILL.md": (
        "devops ci test",
        "devops ci fail-to-pass",
        "devops pr create",
        "devops pr monitor",
        "devops pr ready",
    ),
    "devops-review/SKILL.md": (
        "devops review branch",
        "devops review path",
        "devops review pr",
        "devops review findings",
    ),
    "ask-jev/SKILL.md": ("devops ai ask-jev", "ai_ask_jev"),
    "devops-roadmap/SKILL.md": (
        "devops roadmap intake",
        "devops roadmap return",
        "devops roadmap inbox",
        "devops roadmap explain",
    ),
}


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


@pytest.mark.parametrize("skill", tuple(PROJECT_SKILLS))
def test_every_project_skill_names_its_commands_and_matches_across_roots(skill: str) -> None:
    """Each project skill exists in all three agent roots, holds identical text, and names its
    commands."""
    commands = PROJECT_SKILLS[skill]
    texts = {(REPO_ROOT / root / skill).read_text(encoding="utf-8") for root in SKILL_ROOTS}

    assert len(texts) == 1
    text = next(iter(texts))
    assert [command in text for command in commands] == [True] * len(commands)
