"""PydanticAIDocs capability for fetching official documentation."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool

DEFAULT_PYAI_DOCS_TOPICS: tuple[str, ...] = (
    "agent",
    "capabilities",
    "capability-creation",
    "guardrails",
    "handle-deferred-tool-calls",
    "hooks",
    "include-tool-return-schemas",
    "instrumentation",
    "managed-prompt",
    "media",
    "prepare-tools",
    "prefix-tools",
    "prompt-injection-defender",
    "resolve-model-id",
    "select-model",
    "set-tool-metadata",
    "spend",
    "step-persistence",
    "system-reminders",
    "thread-executor",
    "tools",
    "tools-advanced",
    "toolsets",
)

logger = logging.getLogger(__name__)


class PydanticAIDocs(BaseCapability):
    """Capability that locates and returns Pydantic AI documentation on demand."""

    id: str = "pydantic_ai_docs"
    local_docs_path: Path | None = None
    cache: bool = True
    memoized_docs: dict[str, str] = Field(default_factory=dict)

    def __init__(
        self,
        *,
        local_docs_path: str | Path | None = None,
        cache: bool = True,
        id: str = "pydantic_ai_docs",
    ) -> None:
        p = None
        if local_docs_path is not None:
            p = Path(os.path.expanduser(str(local_docs_path))).resolve()
        elif env_path := os.environ.get("PYDANTIC_AI_HARNESS_DOCS_PATH"):
            p = Path(os.path.expanduser(env_path)).resolve()

        super().__init__(
            id=str(id or "pydantic_ai_docs"),
            local_docs_path=p,
            cache=cache,
        )

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        return [
            "You have access to the read_pyai_docs tool. Consult Pydantic AI documentation before authoring or modifying capabilities, hooks, tools, or toolsets."
        ]

    def _fetch_remote_doc(self, url: str) -> str | None:
        """Attempt to fetch a documentation markdown file over HTTP."""
        try:
            from devops_cli.http.client import new_http_client

            with new_http_client(read_timeout=10.0) as client:
                resp = client.get(url)
                if resp.status_code == 200 and resp.text:
                    return resp.text
        except Exception as exc:
            logger.debug("Remote fetch failed for %s: %s", url, exc)
        return None

    def _read_local_doc(self, local_file: Path) -> str | None:
        """Attempt to read local doc file."""
        try:
            return local_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Error reading local doc %s: %s", local_file, e)
            return None

    def read_doc(self, topic: str) -> str:
        """Resolve and read a Pydantic AI documentation topic (local checkout first, then remote)."""
        clean_topic = topic.strip().lower()
        if clean_topic.endswith(".md"):
            clean_topic = clean_topic[:-3]

        if self.cache and clean_topic in self.memoized_docs:
            return self.memoized_docs[clean_topic]

        # 1. Local checkout
        if self.local_docs_path is not None:
            local_file = self.local_docs_path / f"{clean_topic}.md"
            content = self._read_local_doc(local_file) if local_file.is_file() else None
            if content is not None:
                if self.cache:
                    self.memoized_docs[clean_topic] = content
                return content

        # 2. Remote fallback
        url = f"https://raw.githubusercontent.com/pydantic/pydantic-ai/main/docs/{clean_topic}.md"
        content = self._fetch_remote_doc(url)
        if content:
            if self.cache:
                self.memoized_docs[clean_topic] = content
            return content

        local_attempted = (
            f"local path '{self.local_docs_path}/{clean_topic}.md'"
            if self.local_docs_path
            else "no local checkout configured"
        )
        return f"Error: Could not resolve Pydantic AI documentation topic '{topic}'. Tried {local_attempted} and remote URL '{url}'."

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        read_fn = self.read_doc

        def read_pyai_docs(topic: str) -> str:
            """Locate and return Pydantic AI documentation on demand for a topic (e.g. 'capabilities', 'hooks', 'tools', 'toolsets', 'agent')."""
            return read_fn(topic)

        return [
            Tool.from_function(
                read_pyai_docs,
                name="read_pyai_docs",
                description="Fetch official Pydantic AI documentation for a specific topic or component.",
            )
        ]


PyaiDocs = PydanticAIDocs
