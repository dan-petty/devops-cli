"""Native Pydantic AI function signature generation, inspection, and rendering.

Integrates native ``pydantic_ai.function_signature`` (FunctionSignature, FunctionParam,
TypeSignature, and type expressions) to reconstruct and render typed Python function
signatures and referenced TypedDict schemas directly from JSON Schema, Pydantic models,
or executable tools.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

from pydantic_ai.function_signature import (
    FunctionParam,
    FunctionSignature,
    GenericTypeExpr,
    LiteralTypeExpr,
    SimpleTypeExpr,
    SimpleTypeName,
    TypeExpr,
    TypeFieldSignature,
    TypeSignature,
    UnionTypeExpr,
)
from pydantic_ai.tools import Tool

__all__ = (
    "FunctionParam",
    "FunctionSignature",
    "GenericTypeExpr",
    "LiteralTypeExpr",
    "SimpleTypeExpr",
    "SimpleTypeName",
    "TypeExpr",
    "TypeFieldSignature",
    "TypeSignature",
    "UnionTypeExpr",
    "get_tool_signatures",
    "render_signatures",
    "render_tool_interface",
    "signature_from_callable",
    "signature_from_schema",
    "signature_from_tool",
)


def signature_from_schema(
    name: str,
    parameters_schema: dict[str, Any],
    return_schema: dict[str, Any] | None = None,
    description: str | None = None,
    is_async: bool = False,
) -> FunctionSignature:
    """Build a FunctionSignature from JSON schema definitions."""
    sig = FunctionSignature.from_schema(
        name=name,
        parameters_schema=parameters_schema,
        return_schema=return_schema,
    )
    if description is not None:
        sig.description = description
    if is_async:
        sig.is_async = True
    return sig


def signature_from_callable(
    fn: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
    takes_ctx: bool = False,
) -> FunctionSignature:
    """Construct a FunctionSignature directly from any Python callable."""
    tool = Tool(
        fn,
        name=name,
        description=description,
        takes_ctx=takes_ctx,
    )
    schema = tool.function_schema
    sig = FunctionSignature.from_schema(
        name=tool.name,
        parameters_schema=schema.json_schema,
        return_schema=schema.return_schema,
    )
    sig.description = description or tool.description
    sig.is_async = schema.is_async
    return sig


def signature_from_tool(tool: Any) -> FunctionSignature:
    """Extract or construct a FunctionSignature from an AgentTool, Tool, or callable."""
    if isinstance(tool, FunctionSignature):
        return tool

    if hasattr(tool, "to_function_signature") and callable(tool.to_function_signature):
        return tool.to_function_signature()  # type: ignore[no-any-return]

    if hasattr(tool, "function_schema"):
        schema = tool.function_schema
        sig = FunctionSignature.from_schema(
            name=tool.name,
            parameters_schema=schema.json_schema,
            return_schema=schema.return_schema,
        )
        sig.description = getattr(tool, "description", None)
        sig.is_async = getattr(schema, "is_async", False)
        return sig

    if hasattr(tool, "func") and callable(getattr(tool, "func")):
        name = getattr(tool, "name", getattr(tool.func, "__name__", "tool"))
        desc = getattr(tool, "description", None)
        takes_ctx = getattr(tool, "takes_ctx", False)
        try:
            return signature_from_callable(
                tool.func, name=name, description=desc, takes_ctx=takes_ctx
            )
        except Exception:
            params = getattr(tool, "parameters", {})
            if isinstance(params, dict) and "properties" in params and "type" in params:
                schema_dict = params
            else:
                schema_dict = {
                    "type": "object",
                    "properties": {p: {"type": "string"} for p in params},
                    "required": list(params.keys()),
                }
            return signature_from_schema(name=name, parameters_schema=schema_dict, description=desc)

    if callable(tool):
        return signature_from_callable(tool)

    raise TypeError(f"Unsupported tool type for function signature extraction: {type(tool)}")


def get_tool_signatures(tools: Sequence[Any]) -> list[FunctionSignature]:
    """Extract FunctionSignatures for a sequence of tools or callables."""
    return [signature_from_tool(t) for t in tools]


def render_signatures(
    signatures: Sequence[FunctionSignature],
    *,
    body: str = "...",
    include_type_defs: bool = True,
) -> str:
    """Render Python code blocks for signatures and their referenced TypedDict schemas."""
    sig_list = list(signatures)
    if not sig_list:
        return ""

    conflicts = FunctionSignature.get_conflicting_type_names(sig_list)
    parts: list[str] = []

    if include_type_defs:
        type_defs = FunctionSignature.render_type_definitions(sig_list, conflicts)
        parts.extend(type_defs)

    for s in sig_list:
        rendered = s.render(
            body=body,
            description=s.description,
            is_async=s.is_async,
            conflicting_type_names=conflicts,
        )
        parts.append(rendered)

    return "\n\n".join(parts)


def render_tool_interface(
    tools: Sequence[Any],
    *,
    body: str = "...",
    format: Literal["python", "markdown"] = "python",
    include_type_defs: bool = True,
) -> str:
    """Render a clean Python interface representation of tools for prompts or documentation."""
    sigs = get_tool_signatures(tools)
    code = render_signatures(sigs, body=body, include_type_defs=include_type_defs)
    if format == "markdown":
        return f"```python\n{code}\n```"
    return code
