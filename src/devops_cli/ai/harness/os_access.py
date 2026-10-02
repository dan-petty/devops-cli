import inspect
import logging
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.tools import RunContext as NativeRunContext

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool

logger = logging.getLogger(__name__)


class MountDir(BaseModel):
    """Host directory mount configuration: a virtual path, its host path and the access mode."""

    model_config = ConfigDict(extra="ignore")

    virtual_path: str
    host_path: Path | str
    mode: Literal["overlay", "read-write", "read-only"] = "overlay"


class OSAccess(BaseModel):
    """OS access configuration: the environment variables exposed and whether the clock is read."""

    model_config = ConfigDict(extra="ignore")

    environ: dict[str, str] = Field(default_factory=dict)
    allow_clock: bool = True


def _extract_tool_meta(tool_obj: Any) -> tuple[str, str]:
    """Extract tool name and description string."""
    name = getattr(tool_obj, "name", getattr(tool_obj, "__name__", str(tool_obj)))
    desc = getattr(tool_obj, "description", "") or getattr(tool_obj, "__doc__", "") or ""
    return str(name), str(desc)


def _search_tools_by_regex(
    query_list: list[str], all_tools: list[tuple[str, str, Any]]
) -> list[str]:
    """Match tools using regex search against name or description with ReDoS bounds."""
    matched: list[str] = []
    for q in query_list:
        clean_q = str(q).strip()
        if not clean_q or len(clean_q) > 100:
            continue
        try:
            pattern = re.compile(clean_q, re.IGNORECASE)
        except re.error:
            continue
        for name, desc, _ in all_tools:
            if (pattern.search(name) or pattern.search(desc)) and name not in matched:
                matched.append(name)
    return matched


def _search_tools_by_bm25(
    query_list: list[str], all_tools: list[tuple[str, str, Any]]
) -> list[str]:
    """Score and rank tools using BM25-like token overlap."""
    scores: dict[str, float] = {}
    flat_tokens = [t for q in query_list for t in q.lower().split()]
    for name, desc, _ in all_tools:
        doc_text = f"{name} {desc}".lower()
        score = sum(doc_text.count(t) for t in flat_tokens if t in doc_text)
        if score > 0:
            scores[name] = float(score)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [name for name, _ in ranked]


def _search_tools_by_keywords(
    query_list: list[str],
    all_tools: list[tuple[str, str, Any]],
    discovered_tools: set[str],
) -> list[str]:
    """Match tools with undiscovered matches ranked ahead of already-discovered."""
    undiscovered_matches: list[str] = []
    discovered_matches: list[str] = []
    flat_terms = [term.lower() for q in query_list for term in q.split()]

    for name, desc, _ in all_tools:
        doc_text = f"{name} {desc}".lower()
        if any(term in doc_text for term in flat_terms):
            if name in discovered_tools:
                discovered_matches.append(name)
            else:
                undiscovered_matches.append(name)

    return undiscovered_matches + discovered_matches


class ToolSearch(BaseCapability):
    """Capability for dynamic model-driven discovery of searchable tools marked with defer_loading=True."""

    id: str = "tool_search"
    strategy: Any | None = None
    max_results: int = 5
    description: str = "Search for available tools matching keywords or topics when you need functionality not in your initial toolset."
    defer_loading: bool = False
    tool_name: str = "search_tools"
    searchable_tools: list[Any] = Field(default_factory=list)
    discovered_tools: set[str] = Field(default_factory=set)

    def __init__(
        self,
        strategy: Any | None = None,
        *,
        max_results: int = 5,
        id: str = "tool_search",
        tool_name: str = "search_tools",
        description: str | None = None,
        defer_loading: bool = False,
        searchable_tools: Sequence[Any] = (),
    ) -> None:
        resolved_id = str(id or "tool_search")
        resolved_desc = (
            description
            or "Search for available tools matching keywords or topics when you need functionality not in your initial toolset."
        )
        super().__init__(
            id=resolved_id,
            strategy=strategy,
            max_results=max_results,
            description=resolved_desc,
            defer_loading=defer_loading,
            tool_name=tool_name,
            searchable_tools=list(searchable_tools),
            discovered_tools=set(),
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> ToolSearch:  # type: ignore[override]
        """Return a fresh instance so concurrent runs do not share discovered tools."""
        return ToolSearch(
            strategy=self.strategy,
            max_results=self.max_results,
            id=self.id,
            tool_name=self.tool_name,
            description=self.description,
            defer_loading=self.defer_loading,
            searchable_tools=self.searchable_tools,
        )

    def register_tool(self, tool_obj: Any) -> None:
        """Register a deferred or searchable tool definition."""
        self.searchable_tools.append(tool_obj)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def search_tools(
            ctx: NativeRunContext[Any] = None,  # type: ignore[assignment]
            queries: Sequence[str] | str = (),
            **kwargs: Any,
        ) -> dict[str, Any]:
            """Search for deferred tools by keyword, topic, or regex pattern."""
            actual_ctx: NativeRunContext[Any] | None = None
            if isinstance(ctx, (list, tuple, set, str)):
                query_list = [ctx] if isinstance(ctx, str) else list(ctx)
            else:
                actual_ctx = ctx
                if not queries and "queries" in kwargs:
                    queries = kwargs["queries"]
                query_list = [queries] if isinstance(queries, str) else list(queries)

            all_tools: list[tuple[str, str, Any]] = [
                (*_extract_tool_meta(t), t) for t in self.searchable_tools
            ]

            matched_names: list[str] = []
            if callable(self.strategy):
                custom_res = self.strategy(actual_ctx, query_list, [t[2] for t in all_tools])
                if inspect.iscoroutine(custom_res):
                    custom_res = await custom_res
                if isinstance(custom_res, (list, tuple, set)):
                    matched_names = [str(n) for n in custom_res]
                elif isinstance(custom_res, str):
                    matched_names = [custom_res]
            elif self.strategy == "regex":
                matched_names = _search_tools_by_regex(query_list, all_tools)
            elif self.strategy == "bm25":
                matched_names = _search_tools_by_bm25(query_list, all_tools)
            else:
                matched_names = _search_tools_by_keywords(
                    query_list, all_tools, self.discovered_tools
                )

            trimmed = matched_names[: self.max_results]
            for n in trimmed:
                self.discovered_tools.add(n)

            results = []
            tool_dict = {t[0]: t for t in all_tools}
            for n in trimmed:
                if n in tool_dict:
                    name, desc, _ = tool_dict[n]
                    results.append({"name": name, "description": desc})

            return {
                "matched_tools": results,
                "count": len(results),
                "discovered": list(self.discovered_tools),
            }

        return [
            Tool.from_function(
                search_tools,
                name=self.tool_name,
                description="Search for available tools matching keywords or topics when you need functionality not in your initial toolset.",
                takes_ctx=True,
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = self.description or "ToolSearch capability for on-demand tool discovery."
            return [f"ToolSearch [{self.id}]: {desc}"]

        return [
            "Tool Search Capability enabled.\n"
            "Many specialized tools are deferred to save context. "
            "Use `search_tools(queries=[...])` by keyword or topic when you need functionality not in your initial toolset."
        ]
