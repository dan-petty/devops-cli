"""The dry-run plan of a review takes its model endpoint from the configuration (#5345).

The plan names the setting that is not set, and never a host that no setting gives (#1165).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.review.review_plans import plan_review_corpus_generate, plan_review_path

REVIEW_BODY = '{"model": "<review-model>", "target": "src", "pattern": "*"}'
CORPUS_BODY = '{"input": "<corpus-source-files>", "sources": "src"}'


@pytest.mark.parametrize(
    ("ai", "target"),
    [
        pytest.param(
            {"provider": "gateway", "gateway_url": None},
            "<ai.gateway_url>/chat/completions",
            id="gateway-without-url",
        ),
        pytest.param(
            {"provider": "gateway", "gateway_url": "https://gateway.example.com/v1"},
            "https://gateway.example.com/v1/chat/completions",
            id="gateway-with-url",
        ),
        pytest.param(
            {"provider": "ollama", "ollama_urls": []},
            "<ai.ollama_urls>/api/chat",
            id="ollama-without-urls",
        ),
        pytest.param(
            {"provider": "ollama", "ollama_urls": ["http://ollama.example.com:11434/"]},
            "http://ollama.example.com:11434/api/chat",
            id="ollama-with-urls",
        ),
        pytest.param(
            {"provider": "claude"},
            "https://api.anthropic.com/v1/messages",
            id="claude",
        ),
        pytest.param(
            {
                "provider": "ollama",
                "tasks": {
                    "analysis": {
                        "provider": "gateway",
                        "api_base_url": "https://gateway.example.com/v1",
                    }
                },
            },
            "https://gateway.example.com/v1/chat/completions",
            id="analysis-task-provider",
        ),
    ],
)
def test_review_plan_posts_to_the_configured_model_endpoint(
    config: Callable[..., Path], ai: dict[str, Any], target: str
) -> None:
    """The review path plan posts to the endpoint of the analysis task, or names its unset setting."""
    config(ai=ai)

    assert plan_review_path(targets=["src"]) == [
        PlannedRequest(method="POST", target=target, stdin=REVIEW_BODY)
    ]


def test_corpus_plan_names_the_unset_ollama_setting(config: Callable[..., Path]) -> None:
    """The corpus generate plan names `ai.ollama_urls` when no Ollama URL is set."""
    config(ai={"provider": "ollama", "ollama_urls": []})

    assert plan_review_corpus_generate(sources=["src"]) == [
        PlannedRequest(method="POST", target="<ai.ollama_urls>/api/embeddings", stdin=CORPUS_BODY)
    ]
