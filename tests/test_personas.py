"""Tests for AI personas."""

from __future__ import annotations

from devops_cli.ai.personas import PERSONAS, Persona


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

    with pytest.raises(KeyError):
        _ = PERSONAS["nonexistent"]

    with pytest.raises(KeyError):
        _ = PERSONAS[123]  # type: ignore[index]

    # 2. Module __getattr__
    assert len(personas_mod.METADATA_SYSTEM_PROMPT) > 10
    assert len(personas_mod.ANALYZE_PSEUDOCODE_SYSTEM_PROMPT) > 10
    assert len(personas_mod.ANALYZE_PSEUDOCODE_TASK_PROMPT) > 10

    with pytest.raises(AttributeError):
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
