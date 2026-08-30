"""Adapters and toolsets for integrating third-party tools (e.g. LangChain tools and toolkits)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from devops_cli.ai.agents.pydantic_agent import AgentTool, FunctionToolset, Tool


def tool_from_langchain(
    langchain_tool: Any,
    *,
    name: str | None = None,
    description: str | None = None,
    strict: bool | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> Tool:
    """Adapt a LangChain tool instance (BaseTool or StructuredTool) into a Pydantic AI Tool."""
    tool_name = str(name or getattr(langchain_tool, "name", "") or type(langchain_tool).__name__)
    tool_desc = str(description or getattr(langchain_tool, "description", "") or tool_name)

    # Extract runner callback
    run_func: Callable[..., Any]
    if hasattr(langchain_tool, "invoke") and callable(langchain_tool.invoke):

        def _invoke_wrapper(**kwargs: Any) -> Any:
            return langchain_tool.invoke(kwargs)

        run_func = _invoke_wrapper
    elif hasattr(langchain_tool, "run") and callable(langchain_tool.run):

        def _run_wrapper(**kwargs: Any) -> Any:
            return langchain_tool.run(kwargs)

        run_func = _run_wrapper
    elif callable(langchain_tool):
        run_func = langchain_tool
    else:
        raise TypeError(f"Object {langchain_tool!r} is not a valid callable or LangChain tool")

    # Extract schema if available
    args_schema = getattr(langchain_tool, "args_schema", None)
    if args_schema is not None and hasattr(args_schema, "model_json_schema"):
        json_schema = args_schema.model_json_schema()
        return Tool.from_schema(
            run_func,
            name=tool_name,
            description=tool_desc,
            json_schema=json_schema,
            takes_ctx=False,
            strict=strict,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif getattr(langchain_tool, "args", None) and isinstance(langchain_tool.args, dict):
        properties = {
            k: v.get("type", "str") for k, v in langchain_tool.args.items() if isinstance(v, dict)
        }
        return Tool(
            name=tool_name,
            description=tool_desc,
            func=run_func,
            parameters=properties,
            takes_ctx=False,
            strict=strict,
            timeout=timeout,
            max_retries=max_retries,
        )

    return Tool.from_function(
        run_func,
        name=tool_name,
        description=tool_desc,
        takes_ctx=False,
        strict=strict,
        timeout=timeout,
        max_retries=max_retries,
    )


class LangChainToolset(FunctionToolset):
    """Toolset collection wrapping a list of LangChain tools or toolkit."""

    def __init__(
        self,
        tools: list[Any] | None = None,
        *,
        instructions: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        converted_tools: list[Tool] = []
        if tools:
            for t in tools:
                if isinstance(t, Tool):
                    converted_tools.append(t)
                else:
                    converted_tools.append(
                        tool_from_langchain(t, timeout=timeout, max_retries=max_retries)
                    )
        super().__init__(
            tools=converted_tools,
            instructions=instructions,
            timeout=timeout,
            max_retries=max_retries,
        )


LangChainToolset.model_rebuild(_types_namespace={"AgentTool": AgentTool})
