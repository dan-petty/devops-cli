"""The input schemas that the server publishes forbid undeclared parameters, bound numbers and use only keywords a refusal can describe."""

from __future__ import annotations

from tests.support.mcp_client import published_schemas

# Values of the wrong JSON type that pydantic's lax mode converted, by the type the parameter
# declares. `true`, `"1"` and `1.0` all became PR 1, so `review_pr` with `post` commented on it.
# JSON Schema counts `1.0` as an integer, so the sweep holds the check to the stricter reading.
_COERCED_VALUES: dict[str, tuple[object, ...]] = {
    "integer": (True, "1", 1.0),
    "number": (True, "1.5"),
    "boolean": ("true",),
}


_SAMPLE_JSON_TYPES: dict[type, str] = {bool: "boolean", str: "string", float: "number"}


# Keywords a published schema may carry: those a refusal is classified and described by, and
# those that only give structure or a default.
_STRUCTURAL_SCHEMA_KEYWORDS = frozenset(
    {"properties", "items", "default", "title", "description", "additionalProperties"}
)


_NUMERIC_BOUND_KEYWORDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")


def _branches(schema: dict) -> list[dict]:
    """The alternatives a property accepts: its `anyOf` branches, or the property itself."""
    return schema.get("anyOf", [schema])


def _coerced_values(schema: dict) -> list[object]:
    """Wrong-typed values for a property, skipping any of a JSON type it also accepts."""
    accepted = {branch.get("type") for branch in _branches(schema)}
    return [
        value
        for declared in sorted(accepted & set(_COERCED_VALUES))
        for value in _COERCED_VALUES[declared]
        if _SAMPLE_JSON_TYPES[type(value)] not in accepted
    ]


def _is_numeric_bounded(schema: dict) -> bool:
    """Report whether a property publishes a numeric bound on any branch."""
    return any(
        keyword in branch for branch in _branches(schema) for keyword in _NUMERIC_BOUND_KEYWORDS
    )


def _schema_keywords(schema: dict) -> set[str]:
    """Every keyword a schema uses, in itself and in each property, item, branch or definition."""
    nested = [
        *schema.get("properties", {}).values(),
        *schema.get("anyOf", []),
        *schema.get("oneOf", []),
        *schema.get("allOf", []),
        *schema.get("$defs", {}).values(),
        *([schema["items"]] if isinstance(schema.get("items"), dict) else []),
    ]
    return set(schema).union(*map(_schema_keywords, nested))


async def test_every_published_schema_forbids_undeclared_parameters() -> None:
    """`additionalProperties: false` is what makes a hallucinated parameter a refusal.

    It held only through FastMCP's defaults, with nothing asserting it.
    """
    from devops_cli.ai.mcp.server import mcp

    schemas = await published_schemas()
    registered = await mcp._list_tools()
    open_schemas = sorted(
        name for name, schema in schemas.items() if schema.get("additionalProperties") is not False
    )
    assert (len(schemas), open_schemas) == (len(registered), [])


async def test_the_validator_refuses_every_coerced_value_without_running_a_handler(
    record_property, handler_runner
) -> None:
    """Every integer, number and boolean parameter of every tool refuses a coerced value.

    The sweep calls the validator alone, never a handler. How many numeric parameters
    publish a bound is reported, not enforced: bounds per argument class are follow-up work.
    """
    from devops_cli.ai.mcp.argument_contract import schema_violations

    schemas = await published_schemas()
    swept = [
        (tool, name, value)
        for tool, schema in schemas.items()
        for name, prop in schema["properties"].items()
        for value in _coerced_values(prop)
    ]
    unrefused = [
        (tool, name, value)
        for tool, name, value in swept
        if (name, "TYPE_MISMATCH")
        not in {(v.parameter, v.kind) for v in schema_violations(schemas[tool], {name: value})}
    ]
    numeric = [
        prop
        for schema in schemas.values()
        for prop in schema["properties"].values()
        if {"integer", "number"} & {branch.get("type") for branch in _branches(prop)}
    ]
    record_property(
        "numeric_parameters_with_a_published_bound",
        f"{sum(map(_is_numeric_bounded, numeric))}/{len(numeric)}",
    )
    assert (len(swept) > len(schemas) / 2, unrefused, handler_runner.call_count) == (True, [], 0)


async def test_pr_and_issue_numbers_publish_a_positive_bound() -> None:
    """Every PR and issue number takes the strict alias, whose `ge=1` the schema publishes."""
    schemas = await published_schemas()
    numbers = {
        (tool, name): prop
        for tool, schema in schemas.items()
        for name, prop in schema["properties"].items()
        if name in {"number", "pr_number", "issue_number"}
    }
    unbounded = sorted(
        key
        for key, prop in numbers.items()
        if not any(
            branch.get("type") == "integer" and branch.get("minimum") == 1
            for branch in _branches(prop)
        )
    )
    assert (len(numbers), unbounded) == (14, [])


async def test_every_published_keyword_is_one_a_refusal_can_describe() -> None:
    """A refusal reads well only for keywords the kind and bound tables know.

    A `pattern` or `multipleOf` failure is a value of the right type, and the refusal would
    name only that type, telling the caller nothing it can fix. A newly published keyword
    fails here first, so its kind and description are added before it can be refused.
    """
    from devops_cli.config.constants import (
        CONST_JSON_SCHEMA_BOUND_PHRASES,
        CONST_JSON_SCHEMA_VIOLATION_KINDS,
    )

    schemas = await published_schemas()
    published = set().union(*map(_schema_keywords, schemas.values()))
    described = {
        *CONST_JSON_SCHEMA_VIOLATION_KINDS,
        *CONST_JSON_SCHEMA_BOUND_PHRASES,
        *_STRUCTURAL_SCHEMA_KEYWORDS,
    }
    assert (sorted(published - described), {"type", "anyOf", "minimum"} <= published) == (
        [],
        True,
    )


def test_describe_schema_states_what_a_property_accepts() -> None:
    """Expected types are read from the schema's keywords, never from a rejected value."""
    from devops_cli.ai.mcp.argument_contract import describe_schema

    assert [
        describe_schema({"type": "integer", "minimum": 1}),
        describe_schema({"type": "integer", "minimum": 1, "maximum": 10}),
        describe_schema(
            {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]}
        ),
        describe_schema({"enum": ["json", "text"]}),
        describe_schema({"const": "json", "type": "string"}),
        describe_schema({"type": ["string", "null"]}),
        describe_schema({}),
    ] == [
        "integer >= 1",
        "integer >= 1 and <= 10",
        "array of string or null",
        'one of "json", "text"',
        'exactly "json"',
        "string or null",
        "any JSON value",
    ]
