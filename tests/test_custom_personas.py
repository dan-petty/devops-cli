"""Tests for repository-level custom team personas."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.personas import load_custom_repo_persona


def test_load_custom_repo_persona_missing(tmp_path: Path) -> None:
    result = load_custom_repo_persona(tmp_path, "security-lead")
    assert result is None


def test_load_custom_repo_persona_exists(tmp_path: Path) -> None:
    personas_dir = tmp_path / ".devops" / "personas"
    personas_dir.mkdir(parents=True)
    custom_prompt = (
        "You are the Lead Security Architect focusing on Zero Trust and IAM policy rules."
    )
    (personas_dir / "security-lead.md").write_text(custom_prompt, encoding="utf-8")

    persona_def = load_custom_repo_persona(tmp_path, "security-lead")
    assert persona_def is not None
    assert persona_def.name == "security-lead"
    assert persona_def.title == "Custom Persona (Security-Lead)"
    assert custom_prompt in persona_def.system_prompt
    assert custom_prompt in persona_def.chat_prompt
    assert custom_prompt in persona_def.compose_prompt
