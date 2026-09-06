"""Pydantic AI ManagedPrompt capability for dynamically versioned and remotely managed agent prompts."""

from __future__ import annotations

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import RunContext

_PROMPT_INJECTION_TAGS_REGEX = re.compile(
    r"<\/?(?:system|instructions?|prompt|untrusted)[^>]*>",
    re.IGNORECASE,
)


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

    @staticmethod
    def format_xml_variable(
        root_tag: str,
        value: Any,
        item_tag: str = "item",
        include_field_info: Any = False,
    ) -> str:
        """Format an object or mapping as clean XML for template interpolation."""
        from devops_cli.ai.format_prompt import format_as_xml

        return format_as_xml(
            obj=value,
            root_tag=root_tag,
            item_tag=item_tag,
            include_field_info=include_field_info,
        )

    def render(
        self,
        extra_vars: dict[str, Any] | None = None,
        format_xml_vars: dict[str, Any] | None = None,
    ) -> str:
        """Render the prompt template substituting variables, including XML-formatted variables."""
        template = self.fetch_template()
        if not template:
            return ""

        vars_dict = {**self.template_vars, **(extra_vars or {})}
        if format_xml_vars:
            for k, val in format_xml_vars.items():
                vars_dict[k] = self.format_xml_variable(root_tag=k, value=val)

        rendered = template
        for k, v in vars_dict.items():
            val_clean = _PROMPT_INJECTION_TAGS_REGEX.sub("", str(v))
            rendered = rendered.replace(f"{{{k}}}", val_clean)
        return rendered

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        extra: dict[str, Any] = {}
        if ctx is not None:
            extra["session_id"] = getattr(ctx, "session_id", "")
            extra["model"] = getattr(ctx, "model", "")
        rendered = self.render(extra_vars=extra)
        return [rendered] if rendered else []
