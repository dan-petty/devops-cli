"""The queries of the reference step (#4672): the rule queries that the body of an item gives, and
their merge with the queries of the model reply.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.roadmap.references.queries import merged_queries, rule_queries
from devops_cli.telemetry.instruments import BRAIN_REFERENCES_TOTAL

if TYPE_CHECKING:
    from tests.support.fakes.otlp import FakeCollector

# A key in the form of a provider key, built here so that no test source holds a literal key.
KEY = "sk-proj-" + "a1B2c3D4e5F6g7H8" * 3

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


def test_a_query_that_the_guard_of_the_web_search_refuses_reaches_no_provider(
    otlp: FakeCollector,
) -> None:
    """The guard of the web search refuses a secret, an e-mail address, a private address and an
    internal host name. A query of the reference step passes the same guard, as the text of the
    item and as the plain words that leave the process."""
    body = (
        "Run `ssh admin@192.168.1.5`, `curl http://nas.lan:8080/api` and "
        f"`OPENAI_API_KEY={KEY}`. Use `pydantic-ai`."
    )
    model = ["agent on 10.0.0.7", "typed agent", "mail ops@example.com", f"token {KEY}"]

    rules = rule_queries(body)
    merged = merged_queries(rules, model, limit=3)

    assert (rules, merged, otlp.points(BRAIN_REFERENCES_TOTAL.name)) == (
        ["pydantic-ai"],
        ("pydantic-ai", "typed agent"),
        [({"provider": "step", "result": "refused"}, 6.0)],
    )


def test_a_code_span_with_a_url_is_read_by_the_host_of_the_url(otlp: FakeCollector) -> None:
    body = "Run `curl http://nas.lan/api` and `wget http://192.168.1.5:8080/x`. Use `pydantic-ai`."

    assert (rule_queries(body), otlp.points(BRAIN_REFERENCES_TOTAL.name)) == (
        ["pydantic-ai"],
        [({"provider": "step", "result": "refused"}, 2.0)],
    )
