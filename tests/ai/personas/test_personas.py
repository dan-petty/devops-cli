"""Tests for AI personas."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.personas import PERSONAS, Persona
from tests.support.paths import REPO_ROOT


def test_qa_persona_is_registered() -> None:
    assert Persona.QA in PERSONAS
    assert PERSONAS[Persona.QA].name == "qa"
    assert "test" in PERSONAS[Persona.QA].system_prompt.lower()
    assert "patch" in PERSONAS[Persona.QA].system_prompt.lower()


def test_persona_registry_mapping_and_getattr(tmp_path) -> None:
    """Verify PersonaRegistry mapping interface, module __getattr__, and custom persona loader."""
    import pytest

    import devops_cli.ai.personas as personas_mod
    from devops_cli.ai.personas import load_custom_repo_persona

    # 1. Mapping methods
    assert len(PERSONAS) == len(Persona)
    assert list(PERSONAS.keys()) == list(Persona)
    assert len(list(PERSONAS.values())) == len(Persona)
    assert len(list(PERSONAS.items())) == len(Persona)
    assert "devsecops" in PERSONAS
    assert "invalid_persona" not in PERSONAS
    assert 123 not in PERSONAS
    assert PERSONAS["devsecops"].name == "devsecops"

    with pytest.raises(KeyError, match="nonexistent"):
        _ = PERSONAS["nonexistent"]

    with pytest.raises(KeyError, match="123"):
        _ = PERSONAS[123]  # type: ignore[index]

    # 2. Module __getattr__
    assert len(personas_mod.METADATA_SYSTEM_PROMPT) > 10
    assert len(personas_mod.ANALYZE_PSEUDOCODE_SYSTEM_PROMPT) > 10
    assert len(personas_mod.ANALYZE_PSEUDOCODE_TASK_PROMPT) > 10

    with pytest.raises(AttributeError, match="NON_EXISTENT_PROMPT"):
        _ = getattr(personas_mod, "NON_EXISTENT_PROMPT")

    # 3. load_custom_repo_persona
    custom_dir = tmp_path / ".devops" / "personas"
    custom_dir.mkdir(parents=True)
    custom_file = custom_dir / "infra.md"
    custom_file.write_text("Custom Infrastructure Persona System Prompt", encoding="utf-8")

    custom_persona = load_custom_repo_persona(tmp_path, "infra")
    assert custom_persona is not None
    assert custom_persona.name == "infra"
    assert "Custom Persona (Infra)" in custom_persona.title

    assert load_custom_repo_persona(tmp_path, "../traversal") is None
    assert load_custom_repo_persona(tmp_path, "missing") is None


# =============================================================================
# Prompt rule coverage
# =============================================================================


# =============================================================================
# Chat prompt
# =============================================================================

_PERSONA_FILES = REPO_ROOT / "src" / "devops_cli" / "ai" / "personas"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip()


@pytest.mark.parametrize("persona", list(Persona))
def test_chat_prompt_holds_the_role_the_chat_task_and_the_persona_prompt(
    persona: Persona,
) -> None:
    """Chat sends the persona prompt too, so the challenger debate rules reach chat (#4824)."""
    persona_dir = _PERSONA_FILES / persona.value
    assert PERSONAS[persona].chat_prompt == "\n\n".join(
        (
            _text(persona_dir / "role.md"),
            _text(_PERSONA_FILES.parent / "tasks" / "chat.md"),
            _text(persona_dir / "prompt.md"),
        )
    )
