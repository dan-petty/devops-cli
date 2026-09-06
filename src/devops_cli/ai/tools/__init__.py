"""Agent tools submodule and native Pydantic AI tools integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pydantic_ai.tools import (
    AgentDepsT,
    AgentNativeTool,
    ArgsValidatorFunc,
    DeferredToolResults,
    DocstringFormat,
    NativeToolFunc,
    ObjectJsonSchema,
    RunContext,
    SystemPromptFunc,
    ToolApproved,
    ToolDefinition,
    ToolDenied,
    ToolFuncContext,
    ToolFuncEither,
    ToolFuncPlain,
    ToolParams,
    ToolPrepareFunc,
    ToolSelector,
    ToolSelectorFunc,
    ToolsPrepareFunc,
    matches_tool_selector,
)
from pydantic_ai.tools import (
    DeferredToolRequests as NativeDeferredToolRequests,
)
from pydantic_ai.tools import (
    Tool as NativeTool,
)

from devops_cli.ai.tools.builtin_tools import (
    argo_apps,
    check_threat_intel,
    docker_analyze_layers,
    git_diff,
    git_status,
    k8s_jaeger_status,
    k8s_pods,
    k8s_validate_manifests,
    list_files,
    rag_search,
    read_file,
    scan_bandit,
    scan_gitleaks,
    scan_iac,
    scan_kubelinter,
    scan_osv,
    scan_pluto,
    scan_popeye,
    scan_semgrep,
    scan_trivy,
    scan_uv_audit,
    search_code,
    tf_lint,
)
from devops_cli.ai.tools.mcp_bridge import get_devops_mcp_toolset, get_mcp_agent_tools
from devops_cli.ai.tools.registry import get_default_tools, get_persona_tools


class Tool(NativeTool):
    """Pydantic AI Tool model for registering function tools with rich configuration."""

    def __init__(
        self,
        function: Callable[..., Any] | None = None,
        *,
        takes_ctx: bool | None = None,
        max_retries: int | None = None,
        name: str | None = None,
        description: str | None = None,
        prepare: ToolPrepareFunc[Any] | None = None,
        args_validator: ArgsValidatorFunc[Any, Any] | None = None,
        args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        docstring_format: DocstringFormat = "auto",
        require_parameter_descriptions: bool = False,
        strict: bool | None = None,
        sequential: bool = False,
        requires_approval: bool = False,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
        defer_loading: bool = False,
        include_return_schema: bool | None = None,
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if function is None:
            raise ValueError("A callable function must be provided to Tool.")
        validator = cast(Any, args_validator or args_validator_func)
        self._args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = (
            args_validator_func or (cast(Any, args_validator) if callable(args_validator) else None)
        )
        super().__init__(
            function,
            takes_ctx=takes_ctx,
            max_retries=max_retries,
            name=name,
            description=description,
            prepare=prepare,
            args_validator=validator,
            docstring_format=docstring_format,
            require_parameter_descriptions=require_parameter_descriptions,
            strict=strict,
            sequential=sequential,
            requires_approval=requires_approval,
            metadata=metadata,
            timeout=timeout,
            defer_loading=defer_loading,
            include_return_schema=include_return_schema,
        )
        self._custom_parameters = parameters

    @property
    def parameters(self) -> dict[str, Any]:
        """Parameter schema dictionary."""
        if self._custom_parameters is not None:
            return self._custom_parameters
        if self.function_schema and self.function_schema.json_schema:
            return cast(dict[str, Any], self.function_schema.json_schema.get("properties", {}))
        return {}

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow invoking the underlying tool function directly."""
        return self.function(*args, **kwargs)

    def execute(self, ctx: Any = None, **kwargs: Any) -> Any:
        """Invoke the tool callback with kwargs and optional RunContext."""
        if self.requires_approval and not (ctx and getattr(ctx, "tool_call_approved", False)):
            from devops_cli.exceptions.ai import ApprovalRequired

            raise ApprovalRequired(f"Tool '{self.name}' requires human approval")
        fn = cast(Callable[..., Any], self.function)
        if self.takes_ctx and ctx is not None:
            return fn(ctx, **kwargs)
        return fn(**kwargs)

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate and filter tool arguments against the declared parameter schema."""
        from devops_cli.ai.agents.context import _check_path_traversal

        params = self.parameters
        if not params:
            clean_args = dict(args)
        else:
            valid_params = set(params.keys())
            clean_args = {}
            for k, v in args.items():
                if k in valid_params:
                    _check_path_traversal(k, v)
                    clean_args[k] = v

        if self._args_validator_func is not None:
            validated = self._args_validator_func(clean_args)
            if isinstance(validated, dict):
                clean_args = validated

        return clean_args

    def to_function_signature(self) -> Any:
        """Convert this tool into a native Pydantic AI FunctionSignature."""
        from devops_cli.ai.function_signature import signature_from_callable, signature_from_schema

        try:
            return signature_from_callable(
                self.function,
                name=self.name,
                description=self.description,
                takes_ctx=self.takes_ctx,
            )
        except Exception:
            params = self.parameters or {}
            if isinstance(params, dict) and "properties" in params and "type" in params:
                schema_dict = params
            else:
                schema_dict = {
                    "type": "object",
                    "properties": {p: {"type": "string"} for p in params},
                    "required": list(params.keys()),
                }
            return signature_from_schema(
                name=self.name,
                parameters_schema=schema_dict,
                description=self.description,
            )

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        takes_ctx: bool | None = None,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
        include_return_schema: bool | None = None,
        args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Tool:
        """Construct a Tool instance from a callable."""
        return cls(
            func,
            name=name,
            description=description,
            takes_ctx=takes_ctx,
            strict=strict,
            requires_approval=requires_approval,
            timeout=timeout,
            max_retries=max_retries,
            include_return_schema=include_return_schema,
            args_validator_func=args_validator_func,
            metadata=metadata,
        )

    @classmethod
    def from_schema(  # type: ignore[override]
        cls,
        function: Callable[..., Any],
        name: str = "",
        description: str = "",
        json_schema: dict[str, Any] | None = None,
        *,
        takes_ctx: bool = False,
        strict: bool | None = None,
        requires_approval: bool = False,
        timeout: float | None = None,
        max_retries: int | None = None,
        args_validator_func: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        **kwargs: Any,
    ) -> Tool:
        """Construct a Tool instance from an arbitrary callable and explicit JSON schema."""
        resolved_name = name or kwargs.get("name", getattr(function, "__name__", "tool"))
        resolved_desc = description or kwargs.get("description", "")
        resolved_schema = (
            json_schema or kwargs.get("json_schema") or {"type": "object", "properties": {}}
        )
        return cls(
            function,
            name=resolved_name,
            description=resolved_desc,
            takes_ctx=takes_ctx,
            strict=strict,
            requires_approval=requires_approval,
            timeout=timeout,
            max_retries=max_retries,
            args_validator_func=args_validator_func,
            parameters=resolved_schema.get("properties", {}),
        )


@dataclass
class DeferredToolRequests(NativeDeferredToolRequests):
    """Collection of tool calls pending human approval or external execution."""

    def build_results(
        self,
        *,
        approvals: dict[str, Any] | None = None,
        calls: dict[str, Any] | None = None,
        metadata: dict[str, dict[str, Any]] | None = None,
        approve_all: bool = False,
        deny_all: bool = False,
    ) -> DeferredToolResults:
        """Create a DeferredToolResults object for these requests."""
        appr_map = dict(approvals or {})
        if approve_all:
            for c in self.approvals:
                key = c.tool_call_id or c.tool_name
                if key and key not in appr_map:
                    appr_map[key] = ToolApproved()
        elif deny_all:
            for c in self.approvals:
                key = c.tool_call_id or c.tool_name
                if key and key not in appr_map:
                    appr_map[key] = ToolDenied()
        return super().build_results(
            approvals=appr_map,
            calls=calls,
            metadata=metadata,
            approve_all=False,
        )


def create_tool(
    function: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
    takes_ctx: bool | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    requires_approval: bool = False,
    metadata: dict[str, Any] | None = None,
    args_validator: ArgsValidatorFunc[Any, Any] | None = None,
    docstring_format: DocstringFormat = "auto",
    strict: bool | None = None,
    sequential: bool = False,
    defer_loading: bool = False,
    include_return_schema: bool | None = None,
) -> Tool:
    """Construct a native Tool instance with rich configuration."""
    return Tool(
        function,
        name=name,
        description=description,
        takes_ctx=takes_ctx,
        timeout=timeout,
        max_retries=max_retries,
        requires_approval=requires_approval,
        metadata=metadata,
        args_validator=args_validator,
        docstring_format=docstring_format,
        strict=strict,
        sequential=sequential,
        defer_loading=defer_loading,
        include_return_schema=include_return_schema,
    )


def is_native_tool(val: Any) -> bool:
    """Check whether a value is an instance of native Tool."""
    return isinstance(val, Tool)


def create_tool_definition(
    name: str,
    parameters_json_schema: dict[str, Any],
    *,
    description: str | None = None,
    outer_typed_dict_key: str | None = None,
    strict: bool | None = None,
    sequential: bool = False,
    metadata: dict[str, Any] | None = None,
    timeout: float | None = None,
    defer_loading: bool = False,
    return_schema: dict[str, Any] | None = None,
    include_return_schema: bool | None = None,
    toolset_id: str | None = None,
    capability_id: str | None = None,
) -> ToolDefinition:
    """Construct a model-bound ToolDefinition dataclass."""
    return ToolDefinition(
        name=name,
        parameters_json_schema=parameters_json_schema,
        description=description,
        outer_typed_dict_key=outer_typed_dict_key,
        strict=strict,
        sequential=sequential,
        metadata=metadata or {},
        timeout=timeout,
        defer_loading=defer_loading,
        return_schema=return_schema,
        include_return_schema=include_return_schema,
        toolset_id=toolset_id,
        capability_id=capability_id,
    )


def approve_all_requests(requests: DeferredToolRequests) -> DeferredToolResults:
    """Auto-approve all approval-requesting tool calls."""
    return requests.build_results(approve_all=True)


def deny_all_requests(
    requests: DeferredToolRequests,
    message: str = "The tool call was denied.",
) -> DeferredToolResults:
    """Auto-deny all approval-requesting tool calls with a message."""
    approvals = {
        (c.tool_call_id or c.tool_name): ToolDenied(message=message) for c in requests.approvals
    }
    return requests.build_results(approvals=approvals)


def matches_tool_selector_sync(
    selector: ToolSelector[Any],
    ctx: RunContext[Any],
    tool_def: ToolDefinition,
) -> bool:
    """Synchronous evaluation wrapper for matches_tool_selector."""
    coro = matches_tool_selector(selector, ctx, tool_def)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


__all__ = [
    "AgentDepsT",
    "AgentNativeTool",
    "ArgsValidatorFunc",
    "DeferredToolRequests",
    "DeferredToolResults",
    "DocstringFormat",
    "NativeToolFunc",
    "ObjectJsonSchema",
    "RunContext",
    "SystemPromptFunc",
    "Tool",
    "ToolApproved",
    "ToolDefinition",
    "ToolDenied",
    "ToolFuncContext",
    "ToolFuncEither",
    "ToolFuncPlain",
    "ToolParams",
    "ToolPrepareFunc",
    "ToolSelector",
    "ToolSelectorFunc",
    "ToolsPrepareFunc",
    "approve_all_requests",
    "argo_apps",
    "check_threat_intel",
    "create_tool",
    "create_tool_definition",
    "deny_all_requests",
    "docker_analyze_layers",
    "get_default_tools",
    "get_devops_mcp_toolset",
    "get_mcp_agent_tools",
    "get_persona_tools",
    "git_diff",
    "git_status",
    "is_native_tool",
    "k8s_jaeger_status",
    "k8s_pods",
    "k8s_validate_manifests",
    "list_files",
    "matches_tool_selector",
    "matches_tool_selector_sync",
    "rag_search",
    "read_file",
    "scan_bandit",
    "scan_gitleaks",
    "scan_iac",
    "scan_kubelinter",
    "scan_osv",
    "scan_pluto",
    "scan_popeye",
    "scan_semgrep",
    "scan_trivy",
    "scan_uv_audit",
    "search_code",
    "tf_lint",
]
