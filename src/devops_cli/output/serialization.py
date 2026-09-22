"""One place that turns a command's result into machine-readable output.

Every command with `--json` built its own emission: `write_stdout(json.dumps(x, indent=2)
+ "\n")` in some, `write_stdout(format_json(x) + "\n")` in others, each deciding for itself
whether to call `model_dump()` or `to_dict()` first. 53 of 306 registered commands offered
JSON and none offered YAML, although `format_yaml` has existed the whole time -- because
adding a format meant editing every command that emits one.

`emit_serialized` is the join. A command hands over its payload and the requested format;
adding a third format is a change here rather than in every caller.
"""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_OUTPUT_FORMAT_JSON,
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_OUTPUT_FORMAT_YAML,
    CONST_OUTPUT_FORMATS,
)
from devops_cli.exceptions.validation import ValidationError


def normalize_format(requested: str) -> str:
    """Resolve a requested output format, refusing one that is not supported.

    A misspelled format that silently fell back to a table would send a script parsing the
    output a human-readable table instead, which fails somewhere further away.
    """
    fmt = (requested or CONST_OUTPUT_FORMAT_TABLE).strip().lower()
    if fmt == "yml":
        return CONST_OUTPUT_FORMAT_YAML
    if fmt not in CONST_OUTPUT_FORMATS:
        raise ValidationError(
            f"Unknown output format {requested!r}. Choose one of: "
            f"{', '.join(sorted(CONST_OUTPUT_FORMATS))}."
        )
    return fmt


def resolve_format(*, json_output: bool = False, yaml_output: bool = False) -> str:
    """Map the boolean flags commands already expose onto a format name.

    Both flags set is a contradiction rather than a precedence question: the caller asked
    for two mutually exclusive representations and only one can be written.
    """
    if json_output and yaml_output:
        raise ValidationError("Choose either --json or --yaml, not both.")
    if yaml_output:
        return CONST_OUTPUT_FORMAT_YAML
    if json_output:
        return CONST_OUTPUT_FORMAT_JSON
    return CONST_OUTPUT_FORMAT_TABLE


def serialize(payload: Any, fmt: str) -> str:
    """Render a payload in the requested machine-readable format.

    Pydantic models, objects exposing `to_dict()`, and plain structures are all accepted,
    so a caller does not have to remember which of those its own result happens to be.
    """
    from devops_cli.output.formatters.scalars import format_serialized

    to_dict = getattr(payload, "to_dict", None)
    prepared = to_dict() if callable(to_dict) else payload
    return format_serialized(prepared, format_type=normalize_format(fmt))


def emit_serialized(payload: Any, fmt: str) -> None:
    """Write a payload to standard output in the requested format."""
    from devops_cli.output.console import write_stdout

    write_stdout(serialize(payload, fmt) + "\n")


__all__ = [
    "emit_serialized",
    "normalize_format",
    "resolve_format",
    "serialize",
]
