"""Check MCP tool arguments against each tool's published schema, never quoting a value.

FastMCP validates arguments with pydantic in lax mode, so `true`, `"1"` and `1.0` all reached
`review_pr` as PR 1 (#862). The published JSON Schema is checked first and refuses whatever
it does not allow. Its `integer` is read strictly: JSON Schema counts `1.0` as an integer, and
lax pydantic would then pass it to the handler as 1. Pydantic still runs afterwards, and its
refusal becomes the same violations. Both describe a violation from its location and the
schema alone: jsonschema's `message` and pydantic's `input` quote the rejected value, and that
value can be a secret.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from jsonschema import Draft202012Validator, validators  # type: ignore[import-untyped]
from pydantic import ValidationError as PydanticValidationError

from devops_cli.ai.schema_reflection import ArgumentRefusal, ArgumentViolation, format_field_path
from devops_cli.config.constants import (
    CONST_ARGUMENT_CONSTRAINT_VIOLATION,
    CONST_ARGUMENT_HALLUCINATED,
    CONST_ARGUMENT_MISSING,
    CONST_JSON_SCHEMA_BOUND_PHRASES,
    CONST_JSON_SCHEMA_VIOLATION_KINDS,
    CONST_MCP_UNDECLARED_PARAMETER_ECHO_LENGTH,
    CONST_PYDANTIC_VIOLATION_KINDS,
    CONST_REDACTED_LOG_VALUE,
)
from devops_cli.security.sanitizer import mask_secrets

__all__ = [
    "RejectedInputLogFilter",
    "argument_refusal",
    "describe_schema",
    "pydantic_violations",
    "schema_violations",
]


def _is_strict_integer(_checker: object, instance: object) -> bool:
    """Accept only a JSON integer written without a fraction, never `1.0` or a boolean."""
    return isinstance(instance, int) and not isinstance(instance, bool)


# Draft 2020-12, except that `integer` refuses `1.0`, which the draft counts as an integer.
_ArgumentValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_strict_integer),
)


def describe_schema(schema: Mapping[str, Any]) -> str:
    """Say what a JSON Schema accepts, from its keywords alone."""
    if "enum" in schema:
        return "one of " + ", ".join(json.dumps(choice) for choice in schema["enum"])
    if "const" in schema:
        return f"exactly {json.dumps(schema['const'])}"
    branches = schema.get("anyOf") or schema.get("oneOf")
    if branches:
        return " or ".join(describe_schema(branch) for branch in branches)
    bounds = [
        phrase.format(schema[keyword])
        for keyword, phrase in CONST_JSON_SCHEMA_BOUND_PHRASES.items()
        if keyword in schema
    ]
    described = _describe_type(schema)
    return f"{described} {' and '.join(bounds)}" if bounds else described


def _describe_type(schema: Mapping[str, Any]) -> str:
    """Name the JSON type a schema declares, with the item type of an array."""
    declared = schema.get("type")
    if declared is None:
        return "any JSON value"
    if declared == "array" and "items" in schema:
        return f"array of {describe_schema(schema['items'])}"
    return " or ".join(declared) if isinstance(declared, list) else str(declared)


def _violation(
    location: Sequence[str | int], kind: str, schema: Mapping[str, Any] | None
) -> ArgumentViolation:
    """Build one violation. The path is masked and cut, as an undeclared name is caller text."""
    parameter = mask_secrets(format_field_path(location))
    expected = "one of the allowed parameters" if schema is None else describe_schema(schema)
    return ArgumentViolation.of(
        parameter[:CONST_MCP_UNDECLARED_PARAMETER_ECHO_LENGTH], kind, expected
    )


def _schema_kind(error: Any) -> str:
    """Classify a jsonschema error by its keyword, looking inside a union for a failed bound."""
    deciding = next((branch for branch in error.context if branch.validator != "type"), error)
    return CONST_JSON_SCHEMA_VIOLATION_KINDS.get(
        deciding.validator, CONST_ARGUMENT_CONSTRAINT_VIOLATION
    )


def _from_schema_error(error: Any) -> list[ArgumentViolation]:
    """Translate one jsonschema error, splitting a keyword that names several parameters."""
    location = list(error.absolute_path)
    properties = error.schema.get("properties", {})
    if error.validator == "additionalProperties":
        undeclared = [name for name in error.instance if name not in properties]
        return [
            _violation([*location, name], CONST_ARGUMENT_HALLUCINATED, None) for name in undeclared
        ]
    if error.validator == "required":
        absent = [name for name in error.validator_value if name not in error.instance]
        return [
            _violation([*location, name], CONST_ARGUMENT_MISSING, properties.get(name, {}))
            for name in absent
        ]
    return [_violation(location, _schema_kind(error), error.schema)]


def schema_violations(
    schema: Mapping[str, Any], arguments: Mapping[str, Any]
) -> list[ArgumentViolation]:
    """Every way the arguments break the published schema, without the values that break it."""
    errors = _ArgumentValidator(schema).iter_errors(arguments)
    return [violation for error in errors for violation in _from_schema_error(error)]


def pydantic_violations(
    schema: Mapping[str, Any], error: PydanticValidationError
) -> list[ArgumentViolation]:
    """Translate pydantic's refusal, describing each argument from the published schema."""
    properties = schema.get("properties", {})
    return [
        _violation(
            detail["loc"],
            CONST_PYDANTIC_VIOLATION_KINDS.get(detail["type"], CONST_ARGUMENT_CONSTRAINT_VIOLATION),
            properties.get(detail["loc"][0]) if detail["loc"] else schema,
        )
        for detail in error.errors(include_url=False)
    ]


def argument_refusal(
    tool_name: str, schema: Mapping[str, Any], violations: Sequence[ArgumentViolation]
) -> str:
    """Render the envelope for a refused call, listing the parameters the tool declares.

    A parameter that fails several keywords, such as `5` against a string `enum`, keeps only its
    first violation, so it neither inflates the count nor takes another parameter's place.
    """
    first_per_parameter: dict[str, ArgumentViolation] = {}
    for violation in violations:
        first_per_parameter.setdefault(violation.parameter, violation)
    return ArgumentRefusal(
        callee=tool_name,
        violations=list(first_per_parameter.values()),
        allowed_parameters=sorted(schema.get("properties", {})),
    ).format_envelope()


class RejectedInputLogFilter(logging.Filter):
    """Redact the rejected values FastMCP logs when pydantic refuses a call's arguments.

    FastMCP logs pydantic's error list, and every entry carries the `input` it refused, so an
    invalid `vault_set` wrote its `key_values` to the log.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Replace each error entry's `input`, keeping the record and the rest of its detail."""
        if isinstance(record.args, tuple):
            record.args = tuple(_without_inputs(arg) for arg in record.args)
        return True


def _without_inputs(arg: object) -> object:
    """Redact `input` from a list of pydantic error entries, leaving any other argument alone."""
    if not isinstance(arg, list):
        return arg
    return [
        {**entry, "input": CONST_REDACTED_LOG_VALUE}
        if isinstance(entry, dict) and "input" in entry
        else entry
        for entry in arg
    ]
