"""The product dashboard of the LLM gateway metrics (#2164)."""

from __future__ import annotations

import json
from typing import Any

from tests.support.paths import REPO_ROOT

# The labels that grow with each caller pod; the gateway excludes them at the source (#4545, #6439).
DROPPED_LABELS = ("client_ip", "user_agent")

DASHBOARD = REPO_ROOT / "k8s" / "devops" / "dashboards" / "ai-spend.json"


def _named(node: Any, key: str) -> list[str]:
    """Every string value of `key` in a JSON document, at any depth."""
    found: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for name, value in current.items():
                if name == key and isinstance(value, str):
                    found.append(value)
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return found


def _mentions_dropped_label(expression: str) -> bool:
    """Whether a `litellm_` expression names a dropped label."""
    return "litellm_" in expression and any(label in expression for label in DROPPED_LABELS)


def check_no_dashboard_query_uses_the_dropped_labels() -> None:
    """No target expression of the spend dashboard names a dropped label (#4545)."""
    offenders = [
        expression
        for expression in _named(json.loads(DASHBOARD.read_text(encoding="utf-8")), "expr")
        if _mentions_dropped_label(expression)
    ]

    assert offenders == [], f"a query of {DASHBOARD.name} names a dropped label: {offenders}"
