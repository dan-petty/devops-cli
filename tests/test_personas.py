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


# =============================================================================
# Prompt rule coverage
# =============================================================================

# Each entry is a decision the shared review prompt encodes. The prompt was compressed
# from 2225 to roughly 1400 tokens and is sent once per persona per segment, so an edit
# that trims a rule along with the prose is cheap to make and invisible until findings
# regress. These are the markers that make such a removal fail here instead.
_REVIEW_PROMPT_RULES: tuple[str, ...] = (
    "OWASP",
    "AGENTS.md",
    "uv.lock",
    "*.example.*",
    "__all__",
    "headers = {}",
    "CWE-22",
    "CWE-59",
    "is_symlink()",
    "DNS rebinding",
    "CWE-400",
    "CWE-209",
    "threading.RLock",
    "192.0.2.0/24",
    "NetworkPolicy",
    "PEP 758",
    "OpenMetrics",
    "common_hallucinations.json",
    "feedback_dataset.jsonl",
    "NotImplementedError",
    "verification_criteria",
    "invalidation_criteria",
    "ROADMAP.md",
    "APPROVE",
    "sanitize_prompt_injection",
    "mergeable_state",
    "response_repair.py",
)


def test_the_review_prompt_still_carries_every_rule() -> None:
    """Compression must not drop a decision along with the words that stated it."""
    from devops_cli.ai.personas import _TASKS_DIR, _load

    prompt = _load(_TASKS_DIR / "review.md")
    assert [rule for rule in _REVIEW_PROMPT_RULES if rule not in prompt] == []


def test_host_specific_rules_are_marked_as_host_specific() -> None:
    """The prompt forbids imposing this CLI's assumptions on another repository.

    It then named `SqlitePlanStore`, `response_repair.py` and this repo's CI workflow among
    its general inspection rules, so it contradicted itself on every target that is not
    this one. Those rules are still there, under a heading that scopes them.
    """
    from devops_cli.ai.personas import _TASKS_DIR, _load

    prompt = _load(_TASKS_DIR / "review.md")
    scoped = prompt[prompt.index("### 4. When the target is this repository") :]
    assert all(marker in scoped for marker in ("response_repair.py", "mergeable_state"))
