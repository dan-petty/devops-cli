"""Dry-run request plan builders for review commands.

A dry run makes zero external requests and returns the ordered PlannedRequest items.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest


def _get_review_llm_target() -> str:
    """Resolve the target URL for LLM review and evaluation calls."""
    settings = load_settings()
    provider = settings.ai.provider
    if provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        return f"{endpoint.rstrip('/')}/api/chat"
    if provider == "gateway":
        gw = (settings.ai.gateway_url or "https://ai.retric.click").rstrip("/")
        return f"{gw}/v1/chat/completions"
    base = settings.ai.api_base_url or "https://api.openai.com/v1"
    return f"{base.rstrip('/')}/chat/completions"


def _get_review_embedding_target() -> str:
    """Resolve the target URL for text/code embeddings."""
    settings = load_settings()
    provider = settings.ai.provider
    if provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        return f"{endpoint.rstrip('/')}/api/embeddings"
    base = settings.ai.api_base_url or "https://api.openai.com/v1"
    return f"{base.rstrip('/')}/embeddings"


def plan_review_path(
    targets: Sequence[Path | str] | None = None,
    pattern: str = "*",
) -> list[PlannedRequest]:
    """Plan source file review requests."""
    target_str = ", ".join(str(t) for t in targets) if targets else "."
    return [
        PlannedRequest(
            method="POST",
            target=_get_review_llm_target(),
            stdin=f'{{"model": "<review-model>", "target": "{target_str}", "pattern": "{pattern}"}}',
        )
    ]


def plan_review_branch(
    branch: str | None = None,
    base: str | None = None,
) -> list[PlannedRequest]:
    """Plan branch review requests."""
    target_branch = branch or "<current-branch>"
    base_branch = base or "main"
    return [
        PlannedRequest(
            method="POST",
            target=_get_review_llm_target(),
            stdin=f'{{"model": "<review-model>", "branch": "{target_branch}", "base": "{base_branch}"}}',
        )
    ]


def plan_review_pr(
    number: int,
    repo: str | None = None,
    post_comment: bool = False,
) -> list[PlannedRequest]:
    """Plan pull request review requests."""
    target_repo = repo or "<owner/repo>"
    requests = [
        PlannedRequest(
            method="GET",
            target=f"https://api.github.com/repos/{target_repo}/pulls/{number}",
        ),
        PlannedRequest(
            method="POST",
            target=_get_review_llm_target(),
            stdin=f'{{"model": "<review-model>", "pr": {number}, "repo": "{target_repo}"}}',
        ),
    ]
    if post_comment:
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"https://api.github.com/repos/{target_repo}/issues/{number}/comments",
                stdin='{"body": "<review-findings-comment>"}',
                condition="if --post",
            )
        )
    return requests


def plan_review_benchmark(
    targets: Sequence[Path | str] | None = None,
    runs: int = 1,
) -> list[PlannedRequest]:
    """Plan review benchmark execution requests."""
    target_str = ", ".join(str(t) for t in targets) if targets else "."
    return [
        PlannedRequest(
            method="POST",
            target=_get_review_llm_target(),
            stdin=f'{{"model": "<review-model>", "target": "{target_str}", "runs": {runs}}}',
            repeat=f"{runs} runs",
        )
    ]


def plan_review_corpus_generate(
    sources: Sequence[Path | str] | None = None,
    out: Path | str | None = None,
) -> list[PlannedRequest]:
    """Plan synthetic defect corpus generation requests."""
    sources_str = ", ".join(str(s) for s in sources) if sources else "<sources>"
    out_str = f', "out": "{out}"' if out else ""
    return [
        PlannedRequest(
            method="POST",
            target=_get_review_embedding_target(),
            stdin=f'{{"input": "<corpus-source-files>", "sources": "{sources_str}"{out_str}}}',
        )
    ]


def plan_review_corpus_score(
    corpus_dir: Path | str = "",
) -> list[PlannedRequest]:
    """Plan corpus scoring and run recording requests."""
    return [
        PlannedRequest(
            method="POST",
            target=_get_review_llm_target(),
            stdin=f'{{"model": "<eval-model>", "corpus": "{corpus_dir}"}}',
        ),
        PlannedRequest(
            method="valkey",
            target=f"SET devops:review:corpus-score:{Path(corpus_dir).name}",
            condition="if recorded to run store",
        ),
    ]


def plan_review_samples_fetch(
    names: Sequence[str] | None = None,
    category: Any = None,
) -> list[PlannedRequest]:
    """Plan fetching sample repositories at pinned commits."""
    from devops_cli.ai.review.samples import load_sample_catalog

    try:
        catalog = load_sample_catalog()
        samples = catalog.select(names, category)
    except OSError, ValueError:
        samples = []

    if not samples:
        return [
            PlannedRequest(
                method="git",
                target="https://github.com/<sample-repository>",
                argv=("git", "fetch", "--quiet", "--depth", "1", "<sample-repository>", "<commit>"),
            )
        ]

    return [
        PlannedRequest(
            method="git",
            target=sample.repository,
            argv=("git", "fetch", "--quiet", "--depth", "1", sample.repository, sample.commit),
        )
        for sample in samples
    ]


def plan_review_samples_validate(
    names: Sequence[str] | None = None,
    category: Any = None,
    review: bool = False,
) -> list[PlannedRequest]:
    """Plan sample repository validation and scoring requests."""
    requests: list[PlannedRequest] = []
    sample_desc = ", ".join(names) if names else "<all-samples>"
    if review:
        requests.append(
            PlannedRequest(
                method="POST",
                target=_get_review_llm_target(),
                stdin=f'{{"model": "<review-model>", "samples": "{sample_desc}"}}',
            )
        )
    requests.append(
        PlannedRequest(
            method="valkey",
            target=f"SET devops:review:sample-validation:{sample_desc}",
            condition="if recorded to run store",
        )
    )
    return requests


def plan_review_score(
    sessions: Sequence[Path | str] | None = None,
    labels: Path | str | None = None,
) -> list[PlannedRequest]:
    """Plan review session scoring against labels."""
    sess_desc = ", ".join(Path(s).name for s in sessions) if sessions else "<sessions>"
    lbl_desc = Path(labels).name if labels else "<labels>"
    return [
        PlannedRequest(
            method="valkey",
            target=f"SET devops:review:score:{sess_desc}",
            stdin=f'{{"labels": "{lbl_desc}"}}',
            condition="if recorded to run store",
        )
    ]


def plan_review_templates_check(
    template: Sequence[str] | None = None,
    sample: Sequence[str] | None = None,
) -> list[PlannedRequest]:
    """Plan defect templates validation sweep requests."""
    tmpl_desc = ", ".join(template) if template else "<all-templates>"
    return [
        PlannedRequest(
            method="valkey",
            target=f"SET devops:review:template-sweep:{tmpl_desc}",
            condition="if recorded to run store",
        )
    ]
