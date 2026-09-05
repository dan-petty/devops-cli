import ast
import asyncio
import inspect
import json
import logging
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentTool,
    BaseCapability,
    PydanticAgent,
    RunContext,
    Tool,
)
from devops_cli.ai.harness.constants import DEFAULT_ADVISOR_INSTRUCTIONS

logger = logging.getLogger(__name__)


def _extract_agent_md_meta(text: str, default_name: str) -> tuple[str, str, str]:
    """Parse YAML frontmatter (name, description) and instructions body from agent markdown."""
    name = default_name
    description = ""
    instructions = text.strip()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
                if isinstance(fm, dict):
                    name = str(fm.get("name") or default_name)
                    description = str(fm.get("description") or "")
                instructions = parts[2].strip()
            except Exception:
                pass
    return name, description, instructions


def _extract_response_data(resp: Any) -> Any:
    """Extract structured data or string content from response object."""
    raw_data = getattr(resp, "data", getattr(resp, "output", getattr(resp, "content", resp)))
    if isinstance(raw_data, BaseModel):
        return raw_data.model_dump()
    if hasattr(raw_data, "__dict__") and not isinstance(
        raw_data, (str, int, float, bool, list, dict)
    ):
        return dict(vars(raw_data))
    return raw_data


MINIMUM_EFFORT_FLOOR: str = "low"


def clamp_effort(effort: Any) -> Any:
    """Clamp reasoning/thinking effort to supported tiers with a safety floor."""
    if effort is None or effort is False:
        return MINIMUM_EFFORT_FLOOR
    if effort is True:
        return True
    if str(effort).lower() in ("minimal", "min", "none", "off"):
        return MINIMUM_EFFORT_FLOOR
    return str(effort).lower()


async def _invoke_agent_callable(agent_obj: Any, task: str) -> Any:
    """Invoke an agent object supporting run_async, run, or callable protocols."""
    if hasattr(agent_obj, "run_async") and callable(agent_obj.run_async):
        return await agent_obj.run_async(task)
    if hasattr(agent_obj, "run") and callable(agent_obj.run):
        return agent_obj.run(task)
    if callable(agent_obj):
        return await agent_obj(task) if inspect.iscoroutinefunction(agent_obj) else agent_obj(task)
    return str(agent_obj)


class ModelOption(BaseModel):
    """Model menu option carrying routing hints and model settings."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str | Any
    description: str | None = None
    settings: Any | None = None


class AgentOverride(BaseModel):
    """Override configuration for a disk-loaded sub-agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str | None = None
    effort: str | None = None


class SubAgent(BaseModel):
    """Wrapper defining a callable child sub-agent with per-delegate run controls."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any
    name: str = ""
    description: str = ""
    models: list[str] | None = None
    usage_limits: Any | None = None
    timeout_seconds: float | None = None
    max_calls: int | None = None
    on_failure: str | None = None
    contain_errors: bool | None = None

    def __init__(
        self,
        agent: Any = None,
        *,
        name: str | None = None,
        description: str | None = None,
        models: Sequence[str] | None = None,
        usage_limits: Any | None = None,
        timeout_seconds: float | None = None,
        max_calls: int | None = None,
        on_failure: str | None = None,
        contain_errors: bool | None = None,
        **kwargs: Any,
    ) -> None:
        if "agent" in kwargs:
            actual_agent = kwargs["agent"]
            if name is None and agent is not None:
                name = str(agent)
        else:
            actual_agent = agent

        sub_name = str(name or getattr(actual_agent, "name", "") or "sub_agent")
        sub_desc = str(
            description
            or getattr(actual_agent, "system_prompt", "")
            or getattr(actual_agent, "description", "")
            or sub_name
        )
        super().__init__(
            agent=actual_agent,
            name=sub_name,
            description=sub_desc,
            models=list(models) if models is not None else None,
            usage_limits=usage_limits,
            timeout_seconds=timeout_seconds,
            max_calls=max_calls,
            on_failure=on_failure,
            contain_errors=contain_errors,
        )


def _try_load_disk_agent(md_file: Path, seen_names: set[str]) -> SubAgent | None:
    """Attempt to parse and instantiate a SubAgent from a markdown specification."""
    try:
        text = md_file.read_text(encoding="utf-8")
        name, description, instructions = _extract_agent_md_meta(text, md_file.stem)
        if name in seen_names:
            return None
        seen_names.add(name)
        child: PydanticAgent[Any, Any] = PydanticAgent(
            client=None, name=name, system_prompt=instructions
        )
        return SubAgent(agent=child, name=name, description=description or f"Sub-agent {name}")
    except Exception:
        return None


class SubAgents(BaseCapability):
    """Capability allowing an orchestrator agent to delegate sub-tasks to named child agents."""

    id: str = "sub_agents"
    agents: list[SubAgent] = Field(default_factory=list)
    models: dict[str, str | ModelOption] = Field(default_factory=dict)
    agent_folders: str | list[Path | str] | None = "agents"
    agent_overrides: dict[str, AgentOverride] = Field(default_factory=dict)
    tool_resolver: Any = None
    forward_usage: bool = True
    inherit_tools: bool = False
    shared_capabilities: list[Any] = Field(default_factory=list)
    event_stream_handler: Any = None
    tool_name: str = "delegate_task"
    tool_retries: int | None = 2
    contain_errors: bool = False
    call_counts: dict[str, int] = Field(default_factory=lambda: defaultdict(int))

    def __init__(
        self,
        *,
        agents: Sequence[SubAgent] = (),
        models: Mapping[str, str | ModelOption] | None = None,
        agent_folders: str | Sequence[Path | str] | None = "agents",
        agent_overrides: Mapping[str, AgentOverride] | None = None,
        tool_resolver: Any = None,
        forward_usage: bool = True,
        inherit_tools: bool = False,
        shared_capabilities: Sequence[Any] = (),
        event_stream_handler: Any = None,
        tool_name: str = "delegate_task",
        tool_retries: int | None = 2,
        contain_errors: bool = False,
    ) -> None:
        super().__init__(
            agents=list(agents),
            models=dict(models) if models is not None else {},
            agent_folders=list(agent_folders)
            if isinstance(agent_folders, (list, tuple))
            else agent_folders,
            agent_overrides=dict(agent_overrides) if agent_overrides is not None else {},
            tool_resolver=tool_resolver,
            forward_usage=forward_usage,
            inherit_tools=inherit_tools,
            shared_capabilities=list(shared_capabilities),
            event_stream_handler=event_stream_handler,
            tool_name=tool_name,
            tool_retries=tool_retries,
            contain_errors=contain_errors,
            call_counts=defaultdict(int),
        )

    def load_disk_agents(self) -> list[SubAgent]:
        """Auto-load markdown agent definitions from conventional or configured folders."""
        if self.agent_folders is None:
            return []

        search_dirs: list[Path] = []
        if isinstance(self.agent_folders, str):
            folder_name = self.agent_folders
            cwd = Path.cwd()
            home = Path.home()
            for root in (cwd, home):
                ag_dir = root / ".agents" / folder_name
                cl_dir = root / ".claude" / folder_name
                if ag_dir.is_dir():
                    search_dirs.append(ag_dir)
                elif cl_dir.is_dir():
                    search_dirs.append(cl_dir)
        elif isinstance(self.agent_folders, (list, tuple, set, Sequence)):
            for p in self.agent_folders:
                path_obj = Path(str(p))
                if path_obj.is_dir():
                    search_dirs.append(path_obj)

        disk_agents: list[SubAgent] = []
        seen_names: set[str] = set()

        for sdir in search_dirs:
            for md_file in sorted(sdir.glob("*.md")):
                agent = _try_load_disk_agent(md_file, seen_names)
                if agent is not None:
                    disk_agents.append(agent)

        return disk_agents

    def get_all_agents(self) -> list[SubAgent]:
        """Return merged explicit agents and disk-loaded agents, with explicit taking precedence."""
        explicit_names = {sa.name for sa in self.agents}
        disk = [da for da in self.load_disk_agents() if da.name not in explicit_names]
        return list(self.agents) + disk

    def _resolve_delegate_model(self, target: SubAgent, model: str | None) -> str:
        """Resolve the model key to use for sub-agent delegation."""
        if model:
            return model
        if target.models:
            return target.models[0]
        return next(iter(self.models.keys()))

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        all_sub_agents = self.get_all_agents()
        agent_map = {sa.name: sa for sa in all_sub_agents}

        def delegate_task(
            ctx: RunContext[Any] | str | None = None,
            agent_name: str = "",
            task: str = "",
            model: str | None = None,
            **kwargs: Any,
        ) -> str:
            """Delegate a self-contained task to a named sub-agent."""
            kw_ctx = kwargs.get("ctx")
            actual_ctx: RunContext[Any] | None = (
                ctx
                if isinstance(ctx, RunContext)
                else (kw_ctx if isinstance(kw_ctx, RunContext) else None)
            )
            if isinstance(ctx, str):
                actual_agent = ctx
                actual_task = agent_name or str(kwargs.get("task", ""))
            else:
                actual_agent = agent_name or str(kwargs.get("agent_name", ""))
                actual_task = task or str(kwargs.get("task", ""))

            if actual_agent not in agent_map:
                available = list(agent_map.keys())
                return (
                    f"Error: unknown sub-agent '{actual_agent}'. Available sub-agents: {available}"
                )

            target = agent_map[actual_agent]

            # Check max_calls budget
            if target.max_calls is not None:
                current_calls = self.call_counts.get(actual_agent, 0)
                if current_calls >= target.max_calls:
                    return (
                        target.on_failure
                        or f"Budget exhausted: max calls ({target.max_calls}) reached for sub-agent '{actual_agent}'."
                    )
                self.call_counts[actual_agent] = current_calls + 1

            # Validate model if model menu is active
            if self.models:
                chosen_model_key = self._resolve_delegate_model(target, model)
                if chosen_model_key not in self.models:
                    return f"Error: model '{chosen_model_key}' not in model menu {list(self.models.keys())}."
                if target.models and chosen_model_key not in target.models:
                    return f"Error: model '{chosen_model_key}' not allowed for sub-agent '{actual_agent}' (allowed: {target.models})."

            sub = target.agent
            contain = (
                target.contain_errors if target.contain_errors is not None else self.contain_errors
            )

            try:
                if hasattr(sub, "run"):
                    if (
                        self.forward_usage
                        and actual_ctx is not None
                        and getattr(actual_ctx, "usage", None) is not None
                    ):
                        try:
                            resp = sub.run(actual_task, usage=actual_ctx.usage)
                        except TypeError:
                            resp = sub.run(actual_task)
                    else:
                        resp = sub.run(actual_task)
                    return str(getattr(resp, "content", getattr(resp, "output", resp)))
                elif callable(sub):
                    resp = sub(actual_task)
                    return str(resp)
                return str(sub)
            except Exception as exc:
                if target.on_failure:
                    return target.on_failure
                if contain:
                    return f"Sub-agent '{actual_agent}' crashed: {exc}"
                raise

        tools: list[AgentTool | Callable[..., Any]] = [
            Tool.from_function(
                delegate_task,
                name=self.tool_name,
                description="Delegate a self-contained task to a named child sub-agent.",
                takes_ctx=True,
            )
        ]

        # Provide direct named tool delegates for each registered child sub-agent
        for sa in all_sub_agents:
            s_name = sa.name

            def _make_named_delegate(name_key: str) -> Callable[[str], str]:
                def _delegate_named(prompt: str) -> str:
                    """Delegate a subtask to the designated child agent."""
                    return delegate_task(agent_name=name_key, task=prompt)

                return _delegate_named

            tools.append(
                Tool.from_function(
                    _make_named_delegate(s_name),
                    name=f"delegate_to_{s_name}",
                    description=f"Delegate a specialized subtask to child agent '{s_name}': {sa.description}",
                )
            )

        return tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        all_sub_agents = self.get_all_agents()
        if not all_sub_agents:
            return ["SubAgents capability active. No sub-agents currently registered."]

        lines = ["Available Sub-Agents for delegation:"]
        for sa in all_sub_agents:
            model_info = f" (models: {', '.join(sa.models)})" if sa.models else ""
            desc = f": {sa.description}" if sa.description else ""
            lines.append(f"- {sa.name}{desc}{model_info}")

        if self.models:
            lines.append("\nModel Menu:")
            for k, v in self.models.items():
                m_desc = (
                    f" ({v.description})" if isinstance(v, ModelOption) and v.description else ""
                )
                lines.append(f"- {k}{m_desc}")

        return ["\n".join(lines)]


class WorkflowAgent(BaseModel):
    """Wrapper defining a child sub-agent inside a DynamicWorkflow catalog."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Any
    name: str = ""
    description: str = ""
    output_type: type[Any] | None = None

    def __init__(
        self,
        agent: Any,
        *,
        name: str | None = None,
        description: str | None = None,
        output_type: type[Any] | None = None,
    ) -> None:
        sub_name = str(name or getattr(agent, "name", "") or "sub_agent")
        sub_desc = str(
            description
            or getattr(agent, "description", "")
            or getattr(agent, "system_prompt", "")
            or sub_name
        )
        super().__init__(
            agent=agent,
            name=sub_name,
            description=sub_desc,
            output_type=output_type
            or getattr(agent, "output_schema", None)
            or getattr(agent, "output_type", None),
        )


class DynamicWorkflow(BaseCapability):
    """Capability allowing an orchestrator agent to coordinate a catalog of sub-agents via a sandboxed Python script."""

    id: str = "dynamic_workflow"
    agents: list[WorkflowAgent] = Field(default_factory=list)
    tool_name: str = "run_workflow"
    max_agent_calls: int = 50
    max_retries: int = 3
    forward_usage: bool = True
    inherit_model: bool = False
    sub_agent_usage_limits: Any | None = None
    resource_limits: dict[str, Any] | str | None = None
    description: str = ""
    defer_loading: bool = False
    call_counts: dict[str, int] = Field(default_factory=lambda: defaultdict(int))
    completed_previews: list[str] = Field(default_factory=list)

    def __init__(
        self,
        *,
        agents: Sequence[WorkflowAgent | Any] = (),
        tool_name: str = "run_workflow",
        max_agent_calls: int = 50,
        max_retries: int = 3,
        forward_usage: bool = True,
        inherit_model: bool = False,
        sub_agent_usage_limits: Any | None = None,
        resource_limits: dict[str, Any] | str | None = None,
        id: str = "dynamic_workflow",
        description: str | None = None,
        defer_loading: bool = False,
    ) -> None:
        wrapped_agents: list[WorkflowAgent] = []
        for ag in agents:
            if isinstance(ag, WorkflowAgent):
                wrapped_agents.append(ag)
            else:
                wrapped_agents.append(WorkflowAgent(ag))

        resolved_id = str(id or "dynamic_workflow")
        super().__init__(
            id=resolved_id,
            agents=wrapped_agents,
            tool_name=tool_name,
            max_agent_calls=max_agent_calls,
            max_retries=max_retries,
            forward_usage=forward_usage,
            inherit_model=inherit_model,
            sub_agent_usage_limits=sub_agent_usage_limits,
            resource_limits=resource_limits,
            description=str(description or ""),
            defer_loading=defer_loading,
            call_counts=defaultdict(int),
            completed_previews=[],
        )

    def reveal(self, agent: WorkflowAgent | Any) -> None:
        """Add a new sub-agent to the catalog mid-run."""
        wrapped = agent if isinstance(agent, WorkflowAgent) else WorkflowAgent(agent)
        name = wrapped.name
        if not name or not name.isidentifier():
            raise ValueError(f"Invalid agent name identifier: {name!r}")
        if any(a.name == name for a in self.agents):
            raise ValueError(f"Agent name collision: {name!r} already exists in workflow catalog")
        self.agents.append(wrapped)

    async def _execute_sub_agent(self, agent_obj: Any, name_str: str, task: str) -> Any:
        """Execute sub-agent invocation asynchronously with budgeting and error containment."""
        total_calls = sum(self.call_counts.values())
        if total_calls >= self.max_agent_calls:
            preview_summary = "\n".join(self.completed_previews[-20:])
            msg = f"Workflow budget exhausted: reached maximum agent calls ({self.max_agent_calls}).\nCompleted results preview:\n{preview_summary}"
            raise RuntimeError(msg)

        self.call_counts[name_str] = self.call_counts.get(name_str, 0) + 1
        resp = await _invoke_agent_callable(agent_obj, task)
        result_val = _extract_response_data(resp)
        val_preview = str(result_val)[:200]
        self.completed_previews.append(f"[{name_str}]: {val_preview}")
        return result_val

    def _make_sub_agent_caller(self, agent_obj: Any, name_str: str) -> Callable[..., Any]:
        """Construct sandboxed callable wrapper for sub-agent."""

        async def _call_sub_agent(*args: Any, task: str | None = None, **kwargs: Any) -> Any:
            if args:
                raise ValueError(
                    f"Sub-agent '{name_str}' must be called with keyword argument task='...'"
                )
            effective_task = str(task if task is not None else kwargs.get("task", ""))
            return await self._execute_sub_agent(agent_obj, name_str, effective_task)

        return _call_sub_agent

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def run_workflow(code: str) -> Any:
            """Execute a Python workflow script coordinating catalog sub-agents."""
            printed_lines: list[str] = []

            def _custom_print(*args: Any, **kwargs: Any) -> None:
                sep = kwargs.get("sep", " ")
                printed_lines.append(sep.join(str(a) for a in args))

            import datetime
            import math
            import re
            import typing
            import unicodedata

            def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
                allowed_modules: dict[str, Any] = {
                    "asyncio": asyncio,
                    "json": json,
                    "re": re,
                    "math": math,
                    "typing": typing,
                    "unicodedata": unicodedata,
                    "datetime": datetime,
                }
                top = name.split(".")[0]
                if top in allowed_modules:
                    return allowed_modules[top]
                raise ImportError(f"Importing '{name}' is forbidden in sandboxed workflow.")

            # Security: Whitelist allowed modules and provide strict safe builtins
            safe_builtins: dict[str, Any] = {
                "__import__": _safe_import,
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "filter": filter,
                "float": float,
                "format": format,
                "frozenset": frozenset,
                "int": int,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "len": len,
                "list": list,
                "map": map,
                "max": max,
                "min": min,
                "range": range,
                "reversed": reversed,
                "round": round,
                "set": set,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "zip": zip,
            }

            sandbox_env: dict[str, Any] = {
                "__builtins__": safe_builtins,
                "asyncio": asyncio,
                "json": json,
                "re": re,
                "math": math,
                "typing": typing,
                "unicodedata": unicodedata,
                "datetime": datetime,
                "print": _custom_print,
            }

            for wag in self.agents:
                sandbox_env[wag.name] = self._make_sub_agent_caller(wag.agent, wag.name)

            # Parse and compile code with AST security validation
            try:
                parsed = ast.parse(code, mode="exec")
            except SyntaxError as syn_err:
                return f"SyntaxError in workflow script: {syn_err}"

            # AST Security Inspection: block dangerous nodes and dunder access
            forbidden_modules = {
                "os",
                "sys",
                "subprocess",
                "shutil",
                "socket",
                "http",
                "urllib",
                "ctypes",
            }
            for node in ast.walk(parsed):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod_name = (
                        node.module
                        if isinstance(node, ast.ImportFrom)
                        else (node.names[0].name if node.names else "")
                    )
                    top_mod = (mod_name or "").split(".")[0]
                    if top_mod in forbidden_modules or top_mod not in sandbox_env:
                        return f"SecurityError: Importing module '{mod_name}' is forbidden in sandboxed workflow."
                elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                    return f"SecurityError: Accessing private/dunder attribute '{node.attr}' is forbidden."

            last_val_node: ast.expr | None = None
            if parsed.body:
                last_stmt = parsed.body[-1]
                if isinstance(last_stmt, ast.Expr):
                    parsed.body.pop()
                    last_val_node = last_stmt.value

            if last_val_node is not None:
                parsed.body.append(ast.Return(value=last_val_node))
            else:
                parsed.body.append(ast.Return(value=ast.Constant(value=None)))

            fn_def = ast.AsyncFunctionDef(
                name="__dynamic_workflow_runner__",
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

            try:
                compiled = compile(module_ast, filename="<workflow>", mode="exec")
                exec(compiled, sandbox_env)  # nosec B102 - sandboxed execution of validated workflow AST
                runner = sandbox_env["__dynamic_workflow_runner__"]
                res = await runner()
            except Exception as exc:
                preview_summary = "\n".join(self.completed_previews[-20:])
                err_msg = f"RuntimeError in workflow script: {exc}"
                if preview_summary:
                    err_msg += f"\nCompleted call previews:\n{preview_summary}"
                return err_msg

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
                run_workflow,
                name=self.tool_name,
                description="Coordinate a catalog of sub-agents by running a sandboxed Python script.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = (
                self.description
                or "DynamicWorkflow capability for coordinating catalog sub-agents."
            )
            return [f"DynamicWorkflow [{self.id}]: {desc}"]

        lines = [
            "Dynamic Workflow Capability enabled.",
            "You can coordinate sub-agents by calling tool 'run_workflow(code=...)' with an async Python script.",
            "Available sub-agents in catalog (call with 'await name(task=...)'):",
        ]
        for wag in self.agents:
            out_desc = f" -> {wag.output_type.__name__}" if wag.output_type else " -> str"
            desc_text = f": {wag.description}" if wag.description else ""
            lines.append(f"- async def {wag.name}(*, task: str){out_desc}{desc_text}")

        lines.append(
            "\nScript Guidelines:\n"
            "- Use 'await asyncio.gather(...)' for concurrent fan-out.\n"
            "- Pass work with keyword argument 'task=...'.\n"
            "- The value of the last expression in the script becomes the result.\n"
            "- Sub-agent results returning structured data can be accessed via dictionary subscripts."
        )

        return ["\n".join(lines)]


class Advisor(BaseCapability):
    """Let an executor model consult a separate advisor model through a provider-native tool or local fallback."""

    id: str = "advisor"
    model: Any = Field(default="openai:gpt-4o")
    mode: Literal["auto", "native", "local"] = "auto"
    max_uses: int | None = None
    max_tokens: int | None = None
    caching: Literal["5m", "1h"] | None = None
    forward_history: bool = False
    instructions: str = DEFAULT_ADVISOR_INSTRUCTIONS
    description: str = (
        "Consult an advisor model for guidance, code reviews, and specialized feedback."
    )
    defer_loading: bool = False
    current_uses: int = 0

    def __init__(
        self,
        model: Any = "openai:gpt-4o",
        *,
        mode: Literal["auto", "native", "local"] = "auto",
        max_uses: int | None = None,
        max_tokens: int | None = None,
        caching: Literal["5m", "1h"] | None = None,
        forward_history: bool = False,
        instructions: str | None = None,
        description: str | None = None,
        id: str = "advisor",
        defer_loading: bool = False,
    ) -> None:
        if max_uses is not None and max_uses < 1:
            raise ValueError(f"max_uses must be at least 1, got {max_uses}")
        if max_tokens is not None and max_tokens < 1024:
            raise ValueError(f"max_tokens must be at least 1024, got {max_tokens}")

        model_name = str(model)
        if mode == "native":
            if model_name.startswith("openrouter:") and max_uses is not None:
                raise ValueError("OpenRouter native advisor does not support max_uses")
            if caching is not None and not model_name.startswith("anthropic:"):
                raise ValueError("caching is only supported on Anthropic native advisor")

        resolved_id = str(id or "advisor")
        resolved_inst = instructions or DEFAULT_ADVISOR_INSTRUCTIONS
        resolved_desc = (
            description
            or "Consult an advisor model for guidance, code reviews, and specialized feedback."
        )

        super().__init__(
            id=resolved_id,
            model=model,
            mode=mode,
            max_uses=max_uses,
            max_tokens=max_tokens,
            caching=caching,
            forward_history=forward_history,
            instructions=resolved_inst,
            description=resolved_desc,
            defer_loading=defer_loading,
            current_uses=0,
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> Advisor:  # type: ignore[override]
        """Return a fresh capability instance with local usage isolated to this run."""
        return Advisor(
            model=self.model,
            mode=self.mode,
            max_uses=self.max_uses,
            max_tokens=self.max_tokens,
            caching=self.caching,
            forward_history=self.forward_history,
            instructions=self.instructions,
            description=self.description,
            id=self.id,
            defer_loading=self.defer_loading,
        )

    async def _run_advisor_target(self, prompt: str) -> str:
        """Execute advisor model, agent, or client call."""
        model_target = self.model
        if hasattr(model_target, "run_async"):
            resp = await model_target.run_async(prompt)
            return str(_extract_response_data(resp))
        if hasattr(model_target, "run"):
            resp = model_target.run(prompt)
            return str(_extract_response_data(resp))
        if callable(model_target):
            res = (
                await model_target(prompt)
                if inspect.iscoroutinefunction(model_target)
                else model_target(prompt)
            )
            return str(res)

        try:
            from devops_cli.config.settings import get_llm_client

            client = get_llm_client()
            resp = client.chat(f"{self.instructions}\n\nTask: {prompt}")
            return str(getattr(resp, "content", str(resp)))
        except Exception:
            return f"Advisor [{model_target}] guidance: analysis complete for prompt."

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        async def advisor(prompt: str, ctx: RunContext[Any] | None = None) -> str:
            """Consult the specialist advisor model for guidance or critique."""
            if self.max_uses is not None and self.current_uses >= self.max_uses:
                return (
                    f"Maximum advisor consultations ({self.max_uses}) reached for this request. "
                    "Please proceed without further advice."
                )

            self.current_uses += 1
            return await self._run_advisor_target(prompt)

        return [
            Tool.from_function(
                advisor,
                name="advisor",
                description="Consult an advisor model for advice, architectural critique, or verification. Provide the complete context and question in the prompt.",
            )
        ]

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.defer_loading:
            desc = self.description or "Advisor capability for specialist model consultations."
            return [f"Advisor [{self.id}]: {desc}"]

        return [
            f"Advisor Capability enabled.\n"
            f"- Model: {self.model}\n"
            f"- Mode: {self.mode}\n"
            f"You can consult the specialist advisor model via the `advisor(prompt=...)` tool. "
            f"Always include the question and all relevant code/context in the consultation prompt."
        ]
