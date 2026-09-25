"""Lossless structured error reflection engine for Pydantic schema validation retries.

Preserves up to 5 field paths with type violations, input representations, and
prescriptive fix hints, enabling single-turn model self-correction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from devops_cli.config.constants import (
    CONST_MAX_INPUT_VALUE_REPR_LENGTH,
    CONST_MAX_SCHEMA_REFLECTION_ERRORS,
    CONST_SCHEMA_FIX_HINT_TEMPLATES,
)
from devops_cli.models.ai import ChatMessage

__all__ = [
    "SchemaReflectionReport",
    "SchemaViolation",
    "build_schema_reflection_message",
    "extract_schema_reflection",
    "format_field_path",
    "format_schema_validation_error",
    "synthesize_fix_hint",
]


class SchemaViolation(BaseModel):
    """Structured representation of a single field-level schema validation error."""

    field_path: str = Field(description="Dotted/indexed path to the violating field")
    error_type: str = Field(description="Pydantic validation error type code")
    message: str = Field(description="Human-readable violation description")
    input_value: str | None = Field(
        default=None, description="Truncated representation of observed input value"
    )
    fix_hint: str = Field(description="Prescriptive correction instruction for model self-repair")


class SchemaReflectionReport(BaseModel):
    """Aggregate reflection report preserving up to N field paths and prescriptive fix hints."""

    total_errors: int = Field(description="Total number of validation errors encountered")
    violations: list[SchemaViolation] = Field(
        default_factory=list, description="Preserved violations up to max errors limit"
    )
    remaining_count: int = Field(
        default=0, description="Count of remaining errors truncated beyond max errors limit"
    )

    def format_reflection_prompt(self) -> str:
        """Render a structured markdown prompt to guide single-turn model self-correction."""
        header = (
            "Your previous response failed schema validation. Please self-correct the output "
            f"according to the following error report:\n\n"
            f"Found {self.total_errors} schema violation(s):"
        )
        lines = [header]
        for idx, v in enumerate(self.violations, start=1):
            lines.append(f"{idx}. Field: `{v.field_path}`")
            lines.append(f"   Error: {v.message} ({v.error_type})")
            if v.input_value is not None:
                lines.append(f"   Provided: `{v.input_value}`")
            lines.append(f"   Fix Hint: {v.fix_hint}")

        if self.remaining_count > 0:
            lines.append(f"\n... and {self.remaining_count} additional schema violation(s).")

        footer = (
            "\nPlease respond with ONLY the valid JSON object adhering strictly to the schema, "
            "with no markdown explanations or extraneous commentary."
        )
        lines.append(footer)
        return "\n".join(lines)

    def format_error_summary(self) -> str:
        """Render a concise, bounded summary string suitable for logs and exception details."""
        parts = [f"`{v.field_path}`: {v.message} (Fix: {v.fix_hint})" for v in self.violations]
        summary = f"{self.total_errors} schema error(s): " + "; ".join(parts)
        if self.remaining_count > 0:
            summary += f"; ... and {self.remaining_count} more"
        return summary


def format_field_path(loc: Sequence[int | str] | tuple[int | str, ...]) -> str:
    """Format a Pydantic location sequence into canonical dot-and-bracket path notation."""
    if not loc:
        return "root"

    parts: list[str] = []
    for elem in loc:
        if isinstance(elem, int):
            parts.append(f"[{elem}]")
        elif not parts:
            parts.append(str(elem))
        else:
            parts.append(f".{elem}")
    return "".join(parts)


def _bound_input_value_repr(
    val: Any, max_len: int = CONST_MAX_INPUT_VALUE_REPR_LENGTH
) -> str | None:
    """Safely format and bound input value string representation."""
    if val is None:
        return None
    raw_str = repr(val)
    if len(raw_str) > max_len:
        return raw_str[: max_len - 3] + "..."
    return raw_str


def _format_hint_template(template: str, ctx: dict[str, Any], default_msg: str) -> str:
    """Safely interpolate context variables into hint template without raising KeyError."""
    try:
        format_kwargs = {
            "expected": ctx.get("expected", "valid option"),
            "ge": ctx.get("ge", "required minimum"),
            "gt": ctx.get("gt", "required lower bound"),
            "le": ctx.get("le", "required maximum"),
            "lt": ctx.get("lt", "required upper bound"),
            "min_length": ctx.get("min_length", "required minimum length"),
            "max_length": ctx.get("max_length", "required maximum length"),
            "msg": default_msg,
        }
        return template.format(**format_kwargs)
    except Exception:
        return f"Please correct this field to satisfy: {default_msg}."


def synthesize_fix_hint(error_dict: Mapping[str, Any]) -> str:
    """Synthesize a prescriptive, actionable fix hint from a Pydantic error dictionary."""
    err_type = str(error_dict.get("type", ""))
    ctx = error_dict.get("ctx", {})
    if not isinstance(ctx, dict):
        ctx = {}
    msg = str(error_dict.get("msg", "Validation error"))

    template = CONST_SCHEMA_FIX_HINT_TEMPLATES.get(err_type)
    if template:
        return _format_hint_template(template, ctx, msg)

    return f"Please correct this field to satisfy: {msg}."


def _build_violation_from_error(error_dict: Mapping[str, Any]) -> SchemaViolation:
    """Construct a SchemaViolation instance from a raw Pydantic error dictionary."""
    loc = error_dict.get("loc", ())
    err_type = str(error_dict.get("type", "unknown"))
    msg = str(error_dict.get("msg", "Validation error"))
    input_val = _bound_input_value_repr(error_dict.get("input"))
    fix_hint = synthesize_fix_hint(error_dict)

    return SchemaViolation(
        field_path=format_field_path(loc),
        error_type=err_type,
        message=msg,
        input_value=input_val,
        fix_hint=fix_hint,
    )


def extract_schema_reflection(
    exc: ValidationError,
    max_errors: int = CONST_MAX_SCHEMA_REFLECTION_ERRORS,
) -> SchemaReflectionReport:
    """Extract up to max_errors field paths with lossless error structures and prescriptive hints."""
    raw_errors = exc.errors()
    total_errors = len(raw_errors)
    capped_errors = raw_errors[:max_errors]
    remaining = max(0, total_errors - len(capped_errors))

    violations = [_build_violation_from_error(err) for err in capped_errors]

    return SchemaReflectionReport(
        total_errors=total_errors,
        violations=violations,
        remaining_count=remaining,
    )


def format_schema_validation_error(
    exc: ValidationError,
    max_errors: int = CONST_MAX_SCHEMA_REFLECTION_ERRORS,
) -> str:
    """Format a Pydantic ValidationError into a bounded summary string."""
    report = extract_schema_reflection(exc, max_errors=max_errors)
    return report.format_error_summary()


def build_schema_reflection_message(
    error_source: ValidationError | SchemaReflectionReport | str,
    max_errors: int = CONST_MAX_SCHEMA_REFLECTION_ERRORS,
) -> ChatMessage:
    """Construct a user-role ChatMessage containing structured error reflection guidance."""
    if isinstance(error_source, ValidationError):
        report = extract_schema_reflection(error_source, max_errors=max_errors)
        content = report.format_reflection_prompt()
    elif isinstance(error_source, SchemaReflectionReport):
        content = error_source.format_reflection_prompt()
    else:
        content = (
            "Your previous response could not be parsed or validated against the required schema.\n"
            f"Validation Error: {error_source}\n"
            "Please fix the error and respond with ONLY the valid JSON object matching the schema, "
            "with no markdown explanations or extraneous commentary."
        )

    return ChatMessage(role="user", content=content)
