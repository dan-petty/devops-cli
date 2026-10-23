"""Output spec unwrapping and JSON schema extraction for ``pydantic_ai`` output markers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from pydantic_ai.output import NativeOutput, PromptedOutput, TextOutput, ToolOutput

__all__ = (
    "CallableDict",
    "TextOutput",
    "extract_output_json_schema",
    "unwrap_output_spec",
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


def extract_output_json_schema(spec: Any) -> dict[str, Any] | None:  # noqa: C901
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
