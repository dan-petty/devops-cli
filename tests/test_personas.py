"""Tests for AI personas."""

from __future__ import annotations

from pathlib import Path

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
    "DNS rebinding",
    "CWE-400",
    "CWE-209",
    "NotImplementedError",
    "verification_criteria",
    "invalidation_criteria",
    "APPROVE",
)


# Rules true of this repository only, moved from the shared prompt to its `.devops/review.md`,
# which the reviewers receive when they review this repository (#515).
_OWN_REVIEW_CONVENTION_RULES: tuple[str, ...] = (
    "is_symlink()",
    "threading.RLock",
    "NetworkPolicy",
    "PEP 758",
    "OpenMetrics",
    "sanitize_prompt_injection",
    "mergeable_state",
    "response_repair.py",
)
# Removed on purpose (#515): the model never sees the catalog or the feedback dataset, an
# improvement is not a finding, and private-address rules for documentation are a project's own.
_REMOVED_REVIEW_PROMPT_RULES: tuple[str, ...] = (
    "common_hallucinations.json",
    "feedback_dataset.jsonl",
    "ROADMAP.md",
    "192.0.2.0/24",
)


def test_the_review_prompt_still_carries_every_rule() -> None:
    """Compression must not drop a decision along with the words that stated it."""
    from devops_cli.ai.personas import _TASKS_DIR, _load

    prompt = _load(_TASKS_DIR / "review.md")
    own = (Path(__file__).resolve().parents[1] / ".devops/review.md").read_text(encoding="utf-8")
    assert (
        [rule for rule in _REVIEW_PROMPT_RULES if rule not in prompt],
        [rule for rule in _OWN_REVIEW_CONVENTION_RULES if rule not in own],
        [rule for rule in _REMOVED_REVIEW_PROMPT_RULES if rule in prompt],
    ) == ([], [], [])


def test_host_specific_rules_live_in_this_repositorys_conventions() -> None:
    """The shared prompt forbids imposing one project's rules on another.

    It once carried this repository's rules under a heading asking the model to ignore them
    elsewhere, which every other target still received. They now live in this repository's
    `.devops/review.md`, given to reviewers only when this repository is reviewed (#515).
    """
    from devops_cli.ai.personas import _TASKS_DIR, _load

    prompt = _load(_TASKS_DIR / "review.md")
    own = (Path(__file__).resolve().parents[1] / ".devops/review.md").read_text(encoding="utf-8")
    markers = ("response_repair.py", "mergeable_state")
    assert (
        [m for m in markers if m in prompt],
        [m for m in markers if m not in own],
        "When the target is this repository" in prompt,
    ) == ([], [], False)
