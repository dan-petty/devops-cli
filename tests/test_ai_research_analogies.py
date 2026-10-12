"""Tests for cross-domain analogical pattern retriever (devops ai research analogies)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from devops_cli.ai.research.analogies import (
    AnalogicalPatternRetriever,
    compute_dense_similarity,
    compute_structural_vector,
    extract_domain,
    multi_vector_clustering,
    render_analogies_markdown,
    render_analogies_table,
)
from devops_cli.ai.research.models import AnalogyReport, CrossDomainAnalogy
from devops_cli.config.constants import (
    CONST_RAG_KB_PROJECT,
)
from devops_cli.config.defaults import (
    DEFAULT_RAG_DOCS_COLLECTION,
)
from devops_cli.main import app

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_fixture_nodes() -> list[dict[str, Any]]:
    """Fixture knowledge base containing structurally similar but domain-different modules."""
    return [
        {
            "file_path": "kubernetes/reconciler.md",
            "category": "kubernetes",
            "domain": "kubernetes",
            "content": (
                "The Kubernetes controller runs a reconciliation loop checking desired versus observed state. "
                "On transient failure, it executes an exponential backoff retry loop with randomized jitter "
                "to prevent thundering herd across cluster nodes."
            ),
            "vector": [0.1, 0.2, 0.8, 0.05],
        },
        {
            "file_path": "networking/egress_resilience.md",
            "category": "networking",
            "domain": "networking",
            "content": (
                "Network egress client absorbs transient network disconnects using an exponential backoff "
                "retry loop. Configurable jitter intervals and bounded retry attempts protect remote endpoints."
            ),
            "vector": [0.12, 0.18, 0.79, 0.08],
        },
        {
            "file_path": "database/wal_engine.md",
            "category": "database",
            "domain": "database",
            "content": (
                "The database engine enforces ACID durability via write-ahead logging (WAL). "
                "Every state mutation appends a journal commit record before applying changes, "
                "enabling crash recovery and replay."
            ),
            "vector": [0.9, 0.1, 0.05, 0.02],
        },
        {
            "file_path": "event_driven/event_journal.md",
            "category": "events",
            "domain": "events",
            "content": (
                "Event sourcing pipeline maintains an append-only write-ahead log and journal. "
                "Subscribers replay the commit log to reconstruct projections and recover state."
            ),
            "vector": [0.88, 0.15, 0.04, 0.01],
        },
    ]


# =============================================================================
# Criterion 1: CLI Subcommand Invocability & Help
# =============================================================================


def test_analogies_cli_help() -> None:
    """Criterion 1: Subcommand is registered under ai research and --help exits 0 with option details."""
    result = runner.invoke(app, ["ai", "research", "analogies", "--help"])
    assert (
        result.exit_code,
        "--query" in result.output,
        "--domain" in result.output,
        "--target-domain" in result.output,
        "--min-score" in result.output,
        "--limit" in result.output,
        "--format" in result.output,
        "--dry-run" in result.output,
    ) == (0, True, True, True, True, True, True, True)


# =============================================================================
# Criterion 2: Multi-Vector Topological Clustering Over Fixture Knowledge Base
# =============================================================================


def test_multi_vector_clustering_identifies_cross_domain_isomorphisms(
    sample_fixture_nodes: list[dict[str, Any]],
) -> None:
    """Criterion 2: Multi-vector topological clustering identifies structural pattern isomorphisms

    across domain-different modules in a fixture knowledge base.
    """
    analogies = multi_vector_clustering(sample_fixture_nodes, min_score=0.5, limit=10)
    patterns = [a.pattern for a in analogies]
    pairs = [(a.source_domain, a.target_domain) for a in analogies]

    retry_analogy = next(
        (a for a in analogies if a.pattern == "Exponential Backoff & Retry Loop"), None
    )
    wal_analogy = next(
        (a for a in analogies if a.pattern == "Write-Ahead Logging & Journaling"), None
    )

    assert (
        len(analogies) >= 2,
        "Exponential Backoff & Retry Loop" in patterns,
        "Write-Ahead Logging & Journaling" in patterns,
        retry_analogy is not None and retry_analogy.score >= 0.7,
        wal_analogy is not None and wal_analogy.score >= 0.7,
        all(src != tgt for src, tgt in pairs),
    ) == (True, True, True, True, True, True)


def test_multi_vector_clustering_query_and_domain_constraints(
    sample_fixture_nodes: list[dict[str, Any]],
) -> None:
    """Verify query filtering and domain constraints in topological clustering."""
    retry_only = multi_vector_clustering(sample_fixture_nodes, query="backoff", min_score=0.5)
    db_scoped = multi_vector_clustering(sample_fixture_nodes, source_domain="database")

    assert (
        all("Backoff" in a.pattern for a in retry_only),
        all(a.source_domain == "database" or a.target_domain == "database" for a in db_scoped),
    ) == (True, True)


# =============================================================================
# Criterion 3: Structured Output Format (JSON, YAML, Markdown, Table)
# =============================================================================


def test_analogies_cli_format_json(
    sample_fixture_nodes: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 3: The command surfaces cross-domain analogies as structured JSON output

    naming source, target, pattern, and score.
    """
    monkeypatch.setattr(
        AnalogicalPatternRetriever,
        "retrieve_analogies",
        lambda self, **kwargs: multi_vector_clustering(sample_fixture_nodes, min_score=0.5),
    )

    result = runner.invoke(app, ["ai", "research", "analogies", "--format", "json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert (
        isinstance(data, list),
        len(data) >= 2,
        all({"source", "target", "pattern", "score"}.issubset(item.keys()) for item in data),
        all(isinstance(item["score"], (int, float)) for item in data),
    ) == (True, True, True, True)


def test_analogies_cli_format_yaml_and_markdown(
    sample_fixture_nodes: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify YAML and Markdown serialization of cross-domain analogy outputs."""
    monkeypatch.setattr(
        AnalogicalPatternRetriever,
        "retrieve_analogies",
        lambda self, **kwargs: multi_vector_clustering(sample_fixture_nodes, min_score=0.5),
    )

    yaml_res = runner.invoke(app, ["ai", "research", "analogies", "--format", "yaml"])
    md_res = runner.invoke(app, ["ai", "research", "analogies", "--format", "markdown"])

    yaml_data = yaml.safe_load(yaml_res.stdout)
    assert (
        yaml_res.exit_code,
        md_res.exit_code,
        isinstance(yaml_data, list),
        "# Cross-Domain Analogical Pattern Report" in md_res.stdout,
        "Exponential Backoff & Retry Loop" in md_res.stdout,
    ) == (0, 0, True, True, True)


def test_analogies_cli_dry_run() -> None:
    """Verify dry-run mode returns structured plan without executing retrieval."""
    result = runner.invoke(
        app,
        [
            "ai",
            "research",
            "analogies",
            "--query",
            "retry",
            "--domain",
            "kubernetes",
            "--dry-run",
        ],
    )
    assert (
        result.exit_code,
        '"dry_run": true' in result.output,
        '"action": "retrieve_analogies"' in result.output,
        '"query": "retry"' in result.output,
        '"domain": "kubernetes"' in result.output,
    ) == (0, True, True, True, True)


# =============================================================================
# Criterion 4: Existing RAG Vector Index & Qdrant Seam Leverage
# =============================================================================


def test_retriever_queries_existing_qdrant_seam() -> None:
    """Criterion 4: Operates on existing Knowledge Base RAG collection rather than creating new collections."""
    mock_qdrant = MagicMock()
    mock_qdrant.scroll_points.return_value = [
        {
            "id": "kb-1",
            "payload": {
                "file_path": "kubernetes/reconciler.md",
                "category": "kubernetes",
                "content": "Reconciliation loop with exponential backoff and jitter.",
            },
            "vector": [0.1, 0.2, 0.3],
        },
        {
            "id": "kb-2",
            "payload": {
                "file_path": "networking/client.md",
                "category": "networking",
                "content": "Network client with exponential backoff retry loop.",
            },
            "vector": [0.15, 0.22, 0.28],
        },
    ]

    retriever = AnalogicalPatternRetriever(
        qdrant=mock_qdrant, docs_collection=DEFAULT_RAG_DOCS_COLLECTION
    )
    analogies = retriever.retrieve_analogies(min_score=0.3)

    assert (
        mock_qdrant.scroll_points.called,
        mock_qdrant.scroll_points.call_args[0][0],
        mock_qdrant.scroll_points.call_args[1].get("filter_payload"),
        len(analogies) == 1,
        analogies[0].pattern,
    ) == (
        True,
        DEFAULT_RAG_DOCS_COLLECTION,
        {"project_name": CONST_RAG_KB_PROJECT},
        True,
        "Exponential Backoff & Retry Loop",
    )


def test_retriever_empty_or_offline_fallback() -> None:
    """Verify graceful fallback to bundled knowledge base articles when Qdrant is empty."""
    mock_qdrant = MagicMock()
    mock_qdrant.scroll_points.return_value = []

    retriever = AnalogicalPatternRetriever(qdrant=mock_qdrant)
    analogies = retriever.retrieve_analogies(min_score=0.5, limit=5)

    assert (
        isinstance(analogies, list),
        all(isinstance(a, CrossDomainAnalogy) for a in analogies),
    ) == (True, True)


# =============================================================================
# Helper & Model Invariants
# =============================================================================


def test_extract_domain_helper() -> None:
    """Verify extraction of domain categories from diverse path formats."""
    assert (
        extract_domain(
            "src/devops_cli/ai/knowledge_base/it_domains/topics/kubernetes_architecture.md"
        ),
        extract_domain("it_domains/tools/argo_cd.md"),
        extract_domain("devops_cli/tasks/docker_build.md"),
        extract_domain("networking/client.py"),
        extract_domain("unknown.md", category="custom_category"),
    ) == (
        "kubernetes",
        "argocd",
        "task/docker_build",
        "networking",
        "custom_category",
    )


def test_compute_structural_vector() -> None:
    """Verify structural vector normalization and pattern weights."""
    content = (
        "A controller reconciliation loop with exponential backoff and jitter on transient retry."
    )
    vec = compute_structural_vector(content)

    assert (
        "Exponential Backoff & Retry Loop" in vec,
        "Reconciliation Loop (Convergence)" in vec,
        abs(sum(v**2 for v in vec.values()) - 1.0) < 1e-4,
    ) == (True, True, True)


def test_compute_dense_similarity() -> None:
    """Verify cosine similarity calculation between dense vectors."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert (
        round(compute_dense_similarity(v1, v2), 4),
        round(compute_dense_similarity(v1, v3), 4),
        compute_dense_similarity([], v1),
    ) == (1.0, 0.0, 0.0)


def test_cross_domain_analogy_schema_forbids_extra_fields() -> None:
    """Verify negative tool/model schema invariants: extra fields are forbidden."""
    with pytest.raises(ValidationError):
        CrossDomainAnalogy.model_validate(
            {
                "source": "src/a.py",
                "target": "src/b.py",
                "pattern": "Exponential Backoff & Retry Loop",
                "score": 0.9,
                "unexpected_field": "disallowed",
            }
        )


def test_analogy_report_model() -> None:
    """Verify AnalogyReport model construction and serialization."""
    analogy = CrossDomainAnalogy(
        source="k8s/reconciler.py",
        target="net/client.py",
        pattern="Exponential Backoff & Retry Loop",
        score=0.95,
        source_domain="k8s",
        target_domain="net",
        shared_mechanisms=["backoff", "retry"],
    )
    report = AnalogyReport(
        analogies=[analogy],
        total_pairs_examined=1,
        query="retry",
        domains_analyzed=["k8s", "net"],
    )

    assert (
        report.total_pairs_examined,
        report.query,
        len(report.analogies),
        report.analogies[0].pattern,
    ) == (1, "retry", 1, "Exponential Backoff & Retry Loop")


def test_render_table_and_markdown() -> None:
    """Verify visual rendering helpers construct proper display objects."""
    analogy = CrossDomainAnalogy(
        source="k8s/reconciler.md",
        target="net/client.md",
        pattern="Exponential Backoff & Retry Loop",
        score=0.92,
        source_domain="kubernetes",
        target_domain="networking",
        shared_mechanisms=["backoff", "retry"],
        explanation="Both use exponential backoff.",
    )
    table = render_analogies_table([analogy])
    md = render_analogies_markdown([analogy])

    assert (
        table.title,
        len(table.rows),
        "Exponential Backoff & Retry Loop" in md,
        "k8s/reconciler.md" in md,
    ) == (
        "Cross-Domain Analogical Pattern Isomorphisms",
        1,
        True,
        True,
    )
