import ast
import asyncio
import inspect
import json
import logging
import math
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool

logger = logging.getLogger(__name__)

STANDARD_SANDBOX_MODULES: frozenset[str] = frozenset(
    {
        "asyncio",
        "json",
        "re",
        "math",
        "typing",
        "sys",
        "unicodedata",
        "datetime",
        "print",
    }
)


def _collect_assigned_names(body: list[ast.stmt]) -> set[str]:
    """Collect top-level assigned variable names from AST body."""
    assigned_names: set[str] = set()
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    assigned_names.update(
                        elt.id for elt in target.elts if isinstance(elt, ast.Name)
                    )
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)) and isinstance(stmt.target, ast.Name):
            assigned_names.add(stmt.target.id)
    return assigned_names


class MountDir(BaseModel):
    """Host directory mount configuration for CodeMode sandbox."""

    model_config = ConfigDict(extra="ignore")

    virtual_path: str
    host_path: Path | str
    mode: Literal["overlay", "read-write", "read-only"] = "overlay"


class OSAccess(BaseModel):
    """OS access configuration for CodeMode sandbox."""

    model_config = ConfigDict(extra="ignore")

    environ: dict[str, str] = Field(default_factory=dict)
    allow_clock: bool = True


class CodeMode(BaseCapability):
    """Capability that exposes selected tools as callables inside a run_code sandbox."""

    id: str = "code_mode"
    tools: Any = "all"
    max_retries: int = 3
    max_tool_calls: int = 100
    mount: Any | None = None
    os_access: Any | None = None
    resource_limits: Any | None = None
    dynamic_catalog: bool = False
    description: str = (
        "Execute Python code to call multiple sandboxed tools concurrently or sequentially."
    )
    defer_loading: bool = False
    tool_name: str = "run_code"
    repl_state: dict[str, Any] = Field(default_factory=dict)
    tool_call_count: int = 0
    sandboxed_tools: list[AgentTool | Callable[..., Any]] = Field(default_factory=list)

    def __init__(
        self,
        *,
        tools: Any = "all",
        max_retries: int = 3,
        max_tool_calls: int = 100,
        mount: Any | None = None,
        os_access: Any | None = None,
        resource_limits: Any | None = None,
        dynamic_catalog: bool = False,
        id: str = "code_mode",
        tool_name: str = "run_code",
        description: str | None = None,
        defer_loading: bool = False,
        sandboxed_tools: Sequence[AgentTool | Callable[..., Any]] = (),
    ) -> None:
        resolved_id = str(id or "code_mode")
        resolved_desc = (
            description
            or "Execute Python code to call multiple sandboxed tools concurrently or sequentially."
        )

        super().__init__(
            id=resolved_id,
            tools=tools,
            max_retries=max_retries,
            max_tool_calls=max_tool_calls,
            mount=mount,
            os_access=os_access,
            resource_limits=resource_limits,
            dynamic_catalog=dynamic_catalog,
            description=resolved_desc,
            defer_loading=defer_loading,
            tool_name=tool_name,
            repl_state={},
            tool_call_count=0,
            sandboxed_tools=list(sandboxed_tools),
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> CodeMode:
        """Return a fresh instance so concurrent runs do not share execution state."""
        return CodeMode(
            tools=self.tools,
            max_retries=self.max_retries,
            max_tool_calls=self.max_tool_calls,
            mount=self.mount,
            os_access=self.os_access,
            resource_limits=self.resource_limits,
            dynamic_catalog=self.dynamic_catalog,
            id=self.id,
            tool_name=self.tool_name,
            description=self.description,
            defer_loading=self.defer_loading,
            sandboxed_tools=self.sandboxed_tools,
        )

    def _make_sandboxed_tool_wrapper(self, fn: Any, fn_name: str) -> Callable[..., Any]:
        """Wrap tool with invocation limits for sandboxed execution."""

        async def _sandboxed_tool_call(*args: Any, **kwargs: Any) -> Any:
            if self.tool_call_count >= self.max_tool_calls:
                msg = f"Nested tool call limit exceeded: maximum {self.max_tool_calls} calls reached at '{fn_name}'."
                raise RuntimeError(msg)
            self.tool_call_count += 1
            if inspect.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            if callable(fn):
                return fn(*args, **kwargs)
            return fn

        return _sandboxed_tool_call

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def run_code(code: str, restart: bool = False) -> Any:
            """Execute Python code coordinating sandboxed tools inside an isolated environment."""
            if restart:
                self.repl_state.clear()
                self.tool_call_count = 0

            printed_lines: list[str] = []

            def _custom_print(*args: Any, **kwargs: Any) -> None:
                sep = kwargs.get("sep", " ")
                printed_lines.append(sep.join(str(a) for a in args))

            import datetime
            import re
            import sys
            import typing
            import unicodedata

            sandbox_env: dict[str, Any] = {
                "asyncio": asyncio,
                "json": json,
                "re": re,
                "math": math,
                "typing": typing,
                "sys": sys,
                "unicodedata": unicodedata,
                "datetime": datetime,
                "print": _custom_print,
            }

            # Injected custom OS environment if configured
            if isinstance(self.os_access, OSAccess):
                sandbox_env["_os_environ"] = dict(self.os_access.environ)
            elif callable(self.os_access):
                sandbox_env["_os_access_handler"] = self.os_access

            # Injected mount information if configured
            if self.mount:
                sandbox_env["_mount_config"] = self.mount

            # Populate persistent REPL state
            for k, v in self.repl_state.items():
                if k not in sandbox_env:
                    sandbox_env[k] = v

            for st in self.sandboxed_tools:
                t_name = getattr(st, "name", getattr(st, "__name__", str(st)))
                t_func = getattr(st, "func", st) if not callable(st) else st
                sandbox_env[t_name] = self._make_sandboxed_tool_wrapper(t_func, t_name)

            # Parse and transform AST
            try:
                parsed = ast.parse(code, mode="exec")
            except SyntaxError as syn_err:
                return f"SyntaxError in code mode snippet: {syn_err}"

            last_val_node: ast.expr | None = None
            if parsed.body:
                last_stmt = parsed.body[-1]
                if isinstance(last_stmt, ast.Expr):
                    parsed.body.pop()
                    last_val_node = last_stmt.value

            return_val = last_val_node if last_val_node is not None else ast.Constant(value=None)
            parsed.body.append(ast.Return(value=return_val))

            assigned_names = _collect_assigned_names(parsed.body)
            if assigned_names:
                parsed.body.insert(0, ast.Global(names=list(assigned_names)))

            fn_def = ast.AsyncFunctionDef(
                name="__code_mode_runner__",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=parsed.body,
                decorator_list=[],
            )

            module_ast = ast.Module(body=[fn_def], type_ignores=[])
            ast.fix_missing_locations(module_ast)

            res: Any = None
            try:
                compiled = compile(module_ast, filename="<code_mode>", mode="exec")
                exec(compiled, sandbox_env)  # nosec B102 - sandboxed execution of code_mode AST
                runner = sandbox_env["__code_mode_runner__"]
                res = await runner()
            except Exception as exc:
                return f"RuntimeError in code mode snippet: {exc}"

            # Capture persistent state updates
            tool_names = {
                getattr(st, "name", getattr(st, "__name__", str(st))) for st in self.sandboxed_tools
            }
            for k, v in sandbox_env.items():
                if (
                    not k.startswith("_")
                    and k not in tool_names
                    and k not in STANDARD_SANDBOX_MODULES
                ):
                    self.repl_state[k] = v

            stdout = "\n".join(printed_lines).strip()
            if stdout and res is not None:
                return {"output": stdout, "result": res}
            elif stdout:
                return {"output": stdout}
            elif res is not None:
                return res
            return {}

        return [
            Tool.from_function(
                run_code,
                name=self.tool_name,
                description="Execute Python code to call multiple sandboxed tools concurrently or sequentially.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = self.description or "CodeMode capability for running sandboxed tool workflows."
            return [f"CodeMode [{self.id}]: {desc}"]

        lines = [
            "Code Mode Capability enabled.",
            "You can call sandboxed tools by writing and running Python code with `run_code(code=...)`.",
            "Key instructions:",
            "- Use `await asyncio.gather(...)` to execute multiple tool calls in parallel.",
            "- The value of the last expression in your code is returned automatically as the result.",
            "- REPL variables and imports persist between consecutive `run_code` calls (pass `restart=True` to reset).",
            "- Use `print()` only for supplementary logging.",
        ]
        return ["\n".join(lines)]


def _extract_tool_meta(tool_obj: Any) -> tuple[str, str]:
    """Extract tool name and description string."""
    name = getattr(tool_obj, "name", getattr(tool_obj, "__name__", str(tool_obj)))
    desc = getattr(tool_obj, "description", "") or getattr(tool_obj, "__doc__", "") or ""
    return str(name), str(desc)


def _search_tools_by_regex(
    query_list: list[str], all_tools: list[tuple[str, str, Any]]
) -> list[str]:
    """Match tools using regex search against name or description."""
    matched: list[str] = []
    for q in query_list:
        try:
            pattern = re.compile(q, re.IGNORECASE)
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

    def for_run(self, ctx: RunContext[Any] | None = None) -> ToolSearch:
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
            queries: Sequence[str] | str, ctx: RunContext[Any] | None = None
        ) -> dict[str, Any]:
            """Search for deferred tools by keyword, topic, or regex pattern."""
            query_list = [queries] if isinstance(queries, str) else list(queries)
            all_tools: list[tuple[str, str, Any]] = [
                (*_extract_tool_meta(t), t) for t in self.searchable_tools
            ]

            matched_names: list[str] = []
            if callable(self.strategy):
                custom_res = self.strategy(ctx, query_list, [t[2] for t in all_tools])
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
