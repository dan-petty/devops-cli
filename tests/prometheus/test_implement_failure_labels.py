"""The label `class` of `devops_cli_service_implement_failures_total` (#3476): each value that a
panel or an alert rule matches is a class of the failure taxonomy.

The Service adds 1 to the counter with the value of `FailureClass`. A panel or rule that matches a
value which the taxonomy does not hold (a class that was renamed, or a typo) reads no series and
shows nothing. The test reads the files of `k8s/monitoring` and runs offline.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_SERVICE_METRIC_IMPLEMENT_FAILURES
from devops_cli.roadmap.failure import FailureClass
from tests.support.paths import REPO_ROOT

MONITORING = REPO_ROOT / "k8s" / "monitoring"
CLASSES = {klass.value for klass in FailureClass}
# A matcher of the label `class` and its value: `class="oom"` or `class=~"oom|timeout"`.
MATCHER = re.compile(r'\bclass\s*(?:=~|!~|=|!=)\s*"([^"]*)"')


def _expressions(node: Any) -> Iterator[str]:
    """Every value under the key `expr` in a loaded YAML or JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "expr" and isinstance(value, str):
                yield value
            else:
                yield from _expressions(value)
    elif isinstance(node, list):
        for value in node:
            yield from _expressions(value)


def class_values(expression: str) -> list[str]:
    """The values that `expression` matches against the label `class`, one for each alternative
    of a regex matcher. Empty when the expression does not read the counter."""
    if CONST_SERVICE_METRIC_IMPLEMENT_FAILURES not in expression:
        return []
    return [part for found in MATCHER.findall(expression) for part in found.split("|") if part]


def _documents() -> Iterator[tuple[str, Any]]:
    for path in sorted(MONITORING.rglob("*")):
        name = path.relative_to(REPO_ROOT).as_posix()
        if path.suffix == ".json":
            yield name, json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix in {".yaml", ".yml"}:
            yield name, list(yaml.safe_load_all(path.read_text(encoding="utf-8")))


def test_each_class_value_that_a_panel_or_a_rule_matches_is_a_class_of_the_taxonomy() -> None:
    unknown = [
        f"{name}: {value}"
        for name, document in _documents()
        for expression in _expressions(document)
        for value in class_values(expression)
        if value not in CLASSES
    ]

    assert unknown == []


@pytest.mark.parametrize(
    ("expression", "values"),
    [
        (f'sum(increase({CONST_SERVICE_METRIC_IMPLEMENT_FAILURES}{{class="oom"}}[1h]))', ["oom"]),
        (
            f'{CONST_SERVICE_METRIC_IMPLEMENT_FAILURES}{{class=~"no_change_in_fix|plan_defects"}}',
            ["no_change_in_fix", "plan_defects"],
        ),
        (f"sum by (class) ({CONST_SERVICE_METRIC_IMPLEMENT_FAILURES})", []),
        ('up{class="other"}', []),
    ],
    ids=["equal", "regex", "grouped-only", "other-metric"],
)
def test_the_reader_of_the_matchers_finds_each_value_of_the_counter(
    expression: str, values: list[str]
) -> None:
    assert class_values(expression) == values


def test_the_taxonomy_holds_the_new_classes_that_a_panel_may_match() -> None:
    assert {"no_change_in_fix", "tests_lost", "head_moved", "output_cap"} <= CLASSES
