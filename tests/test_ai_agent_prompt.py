"""Unit tests for Pydantic AI ManagedPrompt capability and versioned prompt registry."""

from __future__ import annotations

from devops_cli.ai.agents import (
    GLOBAL_PROMPT_REGISTRY,
    ManagedPrompt,
    PromptRegistry,
    RunContext,
)


def test_prompt_registry_versioning() -> None:
    """Verify PromptRegistry storing and retrieving versioned prompt templates."""
    registry = PromptRegistry()
    registry.register("devsecops", "Analyze security issues in {project}.", version="v1.0")
    registry.register("devsecops", "Analyze security and compliance in {project}.", version="v2.0")
    registry.register("devsecops", "Latest prompt for {project}.", version="latest")

    assert registry.get("devsecops", "v1.0") == "Analyze security issues in {project}."
    assert registry.get("devsecops", "v2.0") == "Analyze security and compliance in {project}."
    assert registry.get("devsecops", "latest") == "Latest prompt for {project}."
    assert registry.get("devsecops", "nonexistent") is None


def test_managed_prompt_render_and_fallback() -> None:
    """Verify ManagedPrompt variable rendering and fallback template."""
    # 1. Fallback rendering
    managed_fallback = ManagedPrompt(
        name="custom_task",
        fallback_template="You are assisting with {task} in session {session_id}.",
        template_vars={"task": "Kubernetes migration"},
    )

    rendered = managed_fallback.render({"session_id": "sess_123"})
    assert rendered == "You are assisting with Kubernetes migration in session sess_123."

    # 2. Global registry resolution
    GLOBAL_PROMPT_REGISTRY.register(
        "reviewer",
        "Perform review of {repo} using model {model}.",
        version="v1",
    )

    managed_reg = ManagedPrompt(
        name="reviewer",
        version="v1",
        template_vars={"repo": "devops-cli"},
    )
    ctx = RunContext(session_id="s1", model="gpt-4o")
    prompts = managed_reg.get_system_prompt_additions(ctx)
    assert len(prompts) == 1
    assert prompts[0] == "Perform review of devops-cli using model gpt-4o."


def test_managed_prompt_custom_fetcher() -> None:
    """Verify ManagedPrompt with dynamic custom fetcher callback."""

    def remote_logfire_fetcher(name: str, version: str | None) -> str:
        return f"Remote Logfire prompt for {name} ({version}): Perform audit on {{target}}."

    managed_remote = ManagedPrompt(
        name="audit_flow",
        version="production",
        fetcher=remote_logfire_fetcher,
        template_vars={"target": "production cluster"},
    )

    rendered = managed_remote.render()
    assert (
        rendered
        == "Remote Logfire prompt for audit_flow (production): Perform audit on production cluster."
    )
