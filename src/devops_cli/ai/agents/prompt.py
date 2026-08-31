"""Pydantic AI ManagedPrompt capability for dynamically versioned and remotely managed agent prompts."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import RunContext


class PromptRegistry(BaseModel):
    """In-memory or local registry for versioned managed prompts."""

    prompts: dict[str, dict[str, str]] = Field(default_factory=dict)

    def register(self, name: str, template: str, version: str = "latest") -> None:
        """Register a versioned prompt template."""
        if name not in self.prompts:
            self.prompts[name] = {}
        self.prompts[name][version] = template

    def get(self, name: str, version: str = "latest") -> str | None:
        """Retrieve a versioned prompt template."""
        return self.prompts.get(name, {}).get(version)


GLOBAL_PROMPT_REGISTRY = PromptRegistry()


class ManagedPrompt(BaseCapability):
    """Capability that dynamically fetches, versions, and renders agent system instructions."""

    id: str = "managed_prompt"
    name: str = "default_agent_prompt"
    version: str = "latest"
    fallback_template: str = ""
    template_vars: dict[str, Any] = Field(default_factory=dict)
    fetcher: Any = None
    cache_ttl_seconds: float = 300.0
    _cached_template: str | None = None
    _last_fetch_time: float = 0.0

    def fetch_template(self) -> str:
        """Retrieve prompt template from fetcher, global registry, or fallback."""
        now = time.time()
        if self._cached_template is not None and (
            now - self._last_fetch_time < self.cache_ttl_seconds
        ):
            return self._cached_template

        template: str | None = None
        if callable(self.fetcher):
            try:
                template = self.fetcher(self.name, self.version)
            except Exception:
                template = None

        if not template:
            template = GLOBAL_PROMPT_REGISTRY.get(self.name, self.version)

        if not template:
            template = self.fallback_template

        self._cached_template = template or ""
        self._last_fetch_time = now
        return self._cached_template

    def render(self, extra_vars: dict[str, Any] | None = None) -> str:
        """Render the prompt template substituting variables."""
        template = self.fetch_template()
        if not template:
            return ""

        vars_dict = {**self.template_vars, **(extra_vars or {})}
        rendered = template
        for k, v in vars_dict.items():
            rendered = rendered.replace(f"{{{k}}}", str(v))
        return rendered

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        extra: dict[str, Any] = {}
        if ctx is not None:
            extra["session_id"] = getattr(ctx, "session_id", "")
            extra["model"] = getattr(ctx, "model", "")
        rendered = self.render(extra_vars=extra)
        return [rendered] if rendered else []
