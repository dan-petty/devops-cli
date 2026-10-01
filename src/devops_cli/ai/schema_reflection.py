"""Lossless structured error reflection engine for Pydantic schema validation retries.

Preserves up to 5 field paths with type violations, input representations, and
prescriptive fix hints, enabling single-turn model self-correction. The same numbered form
answers a refused call: `ArgumentRefusal` renders it from violations that carry no value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from devops_cli.config.constants import (
    CONST_ARGUMENT_HALLUCINATED,
    CONST_ARGUMENT_MISSING,
    CONST_MAX_INPUT_VALUE_REPR_LENGTH,
    CONST_MAX_SCHEMA_REFLECTION_ERRORS,
)
from devops_cli.models.ai import ChatMessage

__all__ = [
    "ArgumentRefusal",
    "ArgumentViolation",
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


# What to do about a refused argument, by its kind; every other kind is fixed by sending the
# expected value.
_ARGUMENT_FIXES: dict[str, str] = {
    CONST_ARGUMENT_HALLUCINATED: "Remove `{parameter}`; it is not a parameter of this call.",
    CONST_ARGUMENT_MISSING: "Add `{parameter}` as {expected}.",
}
_DEFAULT_ARGUMENT_FIX = "Send `{parameter}` as {expected}."


class ArgumentViolation(BaseModel):
    """One refused argument, described from its schema so the refusal never quotes the value."""

    parameter: str = Field(description="Path of the refused argument, or an undeclared name")
    kind: str = Field(description="Class of mistake, such as HALLUCINATED_PARAM or TYPE_MISMATCH")
    expected: str = Field(description="What the schema accepts at that path")
    fix: str = Field(description="Prescriptive correction that needs no knowledge of the value")

    @classmethod
    def of(cls, parameter: str, kind: str, expected: str) -> ArgumentViolation:
        """Build a violation whose fix follows from its kind."""
        fix = _ARGUMENT_FIXES.get(kind, _DEFAULT_ARGUMENT_FIX)
        return cls(
            parameter=parameter,
            kind=kind,
            expected=expected,
            fix=fix.format(parameter=parameter, expected=expected),
        )


class ArgumentRefusal(BaseModel):
    """A call refused before it ran: its violations and the parameters the callee declares."""

    callee: str = Field(description="Name of the refused tool or function")
    violations: list[ArgumentViolation] = Field(description="Every violation found, in order")
    allowed_parameters: list[str] = Field(description="Parameters the callee declares")

    def format_envelope(self, max_errors: int = CONST_MAX_SCHEMA_REFLECTION_ERRORS) -> str:
        """Render the numbered envelope a model re-issues the call from."""
        shown = self.violations[:max_errors]
        lines = [
            f"Refused `{self.callee}` before it ran: {len(self.violations)} argument violation(s)."
        ]
        for index, violation in enumerate(shown, start=1):
            lines += [
                f"{index}. Parameter: `{violation.parameter}`",
                f"   Kind: {violation.kind}",
                f"   Expected: {violation.expected}",
                f"   Fix: {violation.fix}",
            ]
        if len(self.violations) > len(shown):
            lines.append(f"... and {len(self.violations) - len(shown)} more.")
        allowed = ", ".join(f"`{name}`" for name in sorted(self.allowed_parameters)) or "none"
        lines.append(f"Allowed parameters: {allowed}.")
        lines.append("Re-issue the call with every violation corrected.")
        return "\n".join(lines)


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


def synthesize_fix_hint(error_dict: Mapping[str, Any]) -> str:
    """Synthesize an actionable fix hint directly from Pydantic's validation message."""
    msg = str(error_dict.get("msg", "Validation error"))
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
