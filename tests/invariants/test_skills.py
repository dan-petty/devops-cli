"""The committed skills that call the project commands (#3204): each agent root holds them, and the
roots hold the same text. An agent reads only the skills of its own root, so a skill in one root
reaches one agent."""

from __future__ import annotations

import pytest

from tests.support.paths import REPO_ROOT

SKILL_ROOTS = (".claude/skills", ".agents/skills", ".kilocode/skills")
PROJECT_SKILLS = (
    "new-scaffold/SKILL.md",
    "devops-openspec-new/SKILL.md",
    "devops-pr-ci/SKILL.md",
    "devops-review/SKILL.md",
    "ask-jev/SKILL.md",
    "devops-roadmap/SKILL.md",
)


@pytest.mark.parametrize("skill", PROJECT_SKILLS)
def test_every_project_skill_holds_the_same_text_in_each_root(skill: str) -> None:
    """Each project skill exists in all three agent roots with one text, so no agent reads an
    older copy."""
    texts = {(REPO_ROOT / root / skill).read_text(encoding="utf-8") for root in SKILL_ROOTS}

    assert len(texts) == 1
