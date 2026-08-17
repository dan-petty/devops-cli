"""Tests for AI personas."""

from __future__ import annotations

from devops_cli.ai.personas import PERSONAS, Persona


def test_qa_persona_is_registered() -> None:
    assert Persona.QA in PERSONAS
    assert PERSONAS[Persona.QA].name == "qa"
    assert "test" in PERSONAS[Persona.QA].system_prompt.lower()
    assert "patch" in PERSONAS[Persona.QA].system_prompt.lower()
