"""The queries of the reference step (#4672): the rule queries that the body of an item gives, and
their merge with the queries of the model reply.
"""

from __future__ import annotations

from devops_cli.roadmap.references.queries import merged_queries, rule_queries

BODY = """The job needs an agent.

```python
from pydantic_ai import Agent

agent = Agent("test")
```

Use `pydantic-ai`, as https://pypi.org/project/httpx2/ and
https://github.com/example/agent-tools do. See `--dry-run` and `x`.
"""


def test_the_rule_queries_are_the_imports_then_the_packages_then_the_code_spans() -> None:
    assert rule_queries(BODY) == [
        "from pydantic_ai import Agent",
        "agent-tools",
        "httpx2",
        "pydantic-ai",
        "--dry-run",
    ]


def test_an_import_in_a_code_span_is_an_import_query_and_no_second_span_query() -> None:
    body = "The body holds `from pydantic_ai import Agent` and the code span `pydantic-ai`."

    assert rule_queries(body) == ["from pydantic_ai import Agent", "pydantic-ai"]


def test_a_line_that_only_starts_like_an_import_is_no_import_query() -> None:
    body = "```\nfrom the start of the run\nimport\n```\n"

    assert rule_queries(body) == []


def test_a_query_names_no_search_qualifier_and_repeats_no_other_query() -> None:
    body = 'Read `repo:example/closed "token"`, `Pydantic-AI` and `pydantic-ai`.'

    assert rule_queries(body) == ["repo example/closed token", "Pydantic-AI"]


def test_a_code_span_over_the_length_cap_is_no_query() -> None:
    assert rule_queries(f"Read `{'a' * 121}` and `{'b' * 120}`.") == ["b" * 120]


def test_the_merge_takes_a_rule_query_and_a_model_query_in_turn_up_to_the_limit() -> None:
    rules = ["from pydantic_ai import Agent", "pydantic-ai"]
    model = ["agent tool call", "typed agent", "agent retry", "agent stream"]

    assert merged_queries(rules, model, limit=3) == (
        "from pydantic_ai import Agent",
        "agent tool call",
        "pydantic-ai",
    )


def test_the_merge_of_no_model_query_is_the_rule_queries() -> None:
    assert merged_queries(["a query", "b query"], [], limit=3) == ("a query", "b query")


def test_the_merge_leaves_out_a_model_query_that_repeats_a_rule_query() -> None:
    assert merged_queries(["pydantic-ai"], ["Pydantic-AI", "repo:x/y agent"], limit=3) == (
        "pydantic-ai",
        "repo x/y agent",
    )
