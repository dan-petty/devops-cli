"""Native Pydantic AI output subsystem and domain output specifications.

Re-exports and extends pydantic_ai.output constructs for grammar-constrained
structured outputs, tool-based response schemas, prompted schemas, and functional text processing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, cast

from pydantic import BaseModel
from pydantic_ai.output import (
    NativeOutput,
    OutputContext,
    OutputDataT,
    OutputMode,
    OutputObjectDefinition,
    OutputSpec,
    OutputTypeOrFunction,
    PromptedOutput,
    StructuredDict,
    StructuredOutputMode,
    TextOutput,
    TextOutputFunc,
    ToolOutput,
)

from devops_cli.ai.review_schema import ReviewResult

__all__ = (
    # Native Pydantic AI classes & types
    "ToolOutput",
    "NativeOutput",
    "PromptedOutput",
    "TextOutput",
    "StructuredDict",
    "OutputObjectDefinition",
    "OutputContext",
    "OutputDataT",
    "OutputMode",
    "StructuredOutputMode",
    "OutputSpec",
    "OutputTypeOrFunction",
    "TextOutputFunc",
    # Domain utilities & helpers
    "CallableDict",
    "unwrap_output_spec",
    "extract_output_json_schema",
    "resolve_output_mode",
    "build_output_spec",
    "REVIEW_RESULT_NATIVE",
    "REVIEW_RESULT_TOOL",
    "REVIEW_RESULT_PROMPTED",
    "get_review_output_spec",
)


class CallableDict(dict[str, Any]):
    """Dictionary subclass callable as a method, bridging Pydantic AI agent.output_json_schema() and property access."""

    def __call__(self) -> dict[str, Any]:
        return self


def unwrap_output_spec(spec: Any) -> tuple[Any, ...]:
    """Unwrap any OutputSpec into underlying target Python type(s), callable(s), or dictionary definitions.

    Supports bare BaseModels, NativeOutput, ToolOutput, PromptedOutput, TextOutput, StructuredDict,
    and sequence/union output structures.
    """
    if spec is None:
        return ()

    if isinstance(spec, ToolOutput):
        return (spec.output,)

    if isinstance(spec, (NativeOutput, PromptedOutput)):
        raw_outputs = spec.outputs
        if isinstance(raw_outputs, Sequence) and not isinstance(raw_outputs, (str, bytes)):
            unwrapped_seq: list[Any] = []
            for item in raw_outputs:
                unwrapped_seq.extend(unwrap_output_spec(item))
            return tuple(unwrapped_seq)
        return (raw_outputs,)

    if isinstance(spec, TextOutput):
        return (spec.output_function,)

    if isinstance(spec, (list, tuple, set)):
        unwrapped_list: list[Any] = []
        for item in spec:
            unwrapped_list.extend(unwrap_output_spec(item))
        return tuple(unwrapped_list)

    return (spec,)


def extract_output_json_schema(spec: Any) -> dict[str, Any] | None:
    """Extract standard JSON schema dictionary from any OutputSpec or BaseModel.

    Inspects NativeOutput, ToolOutput, PromptedOutput, StructuredDict, TextOutput, and bare Pydantic models.
    """
    if spec is None:
        return None

    if isinstance(spec, TextOutput):
        return {"type": "string"}

    if isinstance(spec, ToolOutput):
        return extract_output_json_schema(spec.output)

    if isinstance(spec, (NativeOutput, PromptedOutput)):
        unwrapped = unwrap_output_spec(spec)
        if not unwrapped:
            return None
        if len(unwrapped) == 1:
            return extract_output_json_schema(unwrapped[0])
        schemas = [extract_output_json_schema(item) for item in unwrapped]
        valid_schemas = [s for s in schemas if s is not None]
        return {"anyOf": valid_schemas} if valid_schemas else None

    if isinstance(spec, type) and issubclass(spec, BaseModel):
        res = spec.model_json_schema()
        return res if isinstance(res, dict) else None

    if hasattr(spec, "__get_pydantic_json_schema__") or hasattr(
        spec, "__get_pydantic_core_schema__"
    ):
        try:
            from pydantic import TypeAdapter

            return TypeAdapter(spec).json_schema()
        except Exception:
            pass

    if hasattr(spec, "model_json_schema") and callable(spec.model_json_schema):
        res = spec.model_json_schema()
        return res if isinstance(res, dict) else None

    if isinstance(spec, dict):
        return spec

    return None


def resolve_output_mode(
    model_name: str | None = None,
    base_url: str | None = None,
    spec: Any = None,
) -> OutputMode:
    """Determine the optimal output mode ('native', 'tool', 'prompted', 'text') based on endpoint and spec.

    Recommends 'tool' for Ollama Cloud (where upstream grammar constraints are not enforced)
    and 'native' for self-hosted Ollama (v0.5.0+ llama.cpp grammar decoding) and standard models.
    """
    if isinstance(spec, ToolOutput):
        return "tool"
    if isinstance(spec, NativeOutput):
        return "native"
    if isinstance(spec, PromptedOutput):
        return "prompted"
    if isinstance(spec, TextOutput):
        return "text"

    if base_url or model_name:
        from devops_cli.ai.models.ollama import get_recommended_output_mode, is_ollama_cloud

        if base_url and is_ollama_cloud(base_url=base_url, model_name=model_name or ""):
            return "tool"
        if model_name and is_ollama_cloud(model_name=model_name):
            return "tool"
        if base_url or (model_name and ("ollama" in model_name or ":" in model_name)):
            mode = get_recommended_output_mode(base_url=base_url, model_name=model_name)
            return cast(OutputMode, mode)

    return "native"


def build_output_spec(
    schema: Any,
    mode: Literal["auto", "native", "tool", "prompted", "text"] = "auto",
    *,
    name: str | None = None,
    description: str | None = None,
    strict: bool | None = True,
    template: str | None = None,
    max_retries: int | None = None,
) -> Any:
    """Wrap a schema or type in the appropriate OutputSpec marker based on mode.

    If schema is already an OutputSpec marker (NativeOutput, ToolOutput, PromptedOutput, TextOutput),
    it is preserved and returned as-is.
    """
    if isinstance(schema, (NativeOutput, ToolOutput, PromptedOutput, TextOutput)):
        return schema

    selected_mode = "native" if mode == "auto" else mode

    if selected_mode == "native":
        return NativeOutput(
            schema, name=name, description=description, strict=strict, template=template
        )
    if selected_mode == "tool":
        return ToolOutput(
            schema, name=name, description=description, strict=strict, max_retries=max_retries
        )
    if selected_mode == "prompted":
        return PromptedOutput(schema, name=name, description=description, template=template)
    if selected_mode == "text":
        if callable(schema):
            return TextOutput(schema)
        raise ValueError(f"Text output mode requires a callable, got {type(schema)}")

    return NativeOutput(
        schema, name=name, description=description, strict=strict, template=template
    )


# Predefined domain review output specifications
REVIEW_RESULT_NATIVE: NativeOutput[ReviewResult] = NativeOutput(
    ReviewResult,
    name="review_result",
    description="Structured code review analysis and findings",
    strict=True,
)

REVIEW_RESULT_TOOL: ToolOutput[ReviewResult] = ToolOutput(
    ReviewResult,
    name="submit_review",
    description="Submit completed code review findings",
    strict=True,
)

REVIEW_RESULT_PROMPTED: PromptedOutput[ReviewResult] = PromptedOutput(
    ReviewResult,
    name="review_result",
    description="Structured review report",
)


def get_review_output_spec(
    mode: Literal["auto", "native", "tool", "prompted"] = "auto",
    model_name: str | None = None,
    base_url: str | None = None,
) -> Any:
    """Return the optimal OutputSpec for ReviewResult given mode and model endpoint configuration."""
    if mode == "auto":
        resolved = resolve_output_mode(model_name=model_name, base_url=base_url)
        return REVIEW_RESULT_TOOL if resolved == "tool" else REVIEW_RESULT_NATIVE
    if mode == "native":
        return REVIEW_RESULT_NATIVE
    if mode == "tool":
        return REVIEW_RESULT_TOOL
    if mode == "prompted":
        return REVIEW_RESULT_PROMPTED
    return REVIEW_RESULT_NATIVE
