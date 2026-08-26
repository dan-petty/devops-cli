"""Unit tests for the embedding model benchmark runner and evaluation metrics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.benchmark.embedding_runner import (
    EmbeddingBenchmarkRunner,
    cosine_similarity,
)
from devops_cli.ai.benchmark.embedding_tasks import (
    get_embedding_eval_dataset,
)
from devops_cli.commands.benchmark import app
from devops_cli.models.benchmark import (
    EmbeddingBenchmarkReport,
    EmbeddingBenchmarkResult,
)

runner = CliRunner()


def test_cosine_similarity() -> None:
    """Test mathematical accuracy of cosine similarity calculation."""
    # Identical vectors -> 1.0
    assert abs(cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) - 1.0) < 1e-6
    # Orthogonal vectors -> 0.0
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6
    # Opposite vectors -> -1.0
    assert abs(cosine_similarity([1.0, 2.0], [-1.0, -2.0]) - (-1.0)) < 1e-6
    # Dimension mismatch or empty -> 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_embedding_eval_dataset() -> None:
    """Verify evaluation dataset contains balanced categories and non-empty texts."""
    pairs, corpus = get_embedding_eval_dataset()
    assert len(pairs) >= 15
    assert len(corpus) > len(pairs)
    categories = {p.category for p in pairs}
    assert "security" in categories
    assert "kubernetes" in categories
    assert "architecture" in categories
    assert "ci_cd" in categories
    assert "infrastructure" in categories
    for p in pairs:
        assert len(p.query) > 10
        assert len(p.target_passage) > 20


def test_embedding_benchmark_runner_dry_run() -> None:
    """Test end-to-end benchmark execution in dry-run mode."""
    bench_runner = EmbeddingBenchmarkRunner(
        models=["qwen3-embedding:0.6b", "nomic-embed-text:latest", "all-minilm:latest"],
        servers=["http://localhost:11434"],
        is_dry_run=True,
    )
    report = bench_runner.run()

    assert isinstance(report, EmbeddingBenchmarkReport)
    assert len(report.models) == 3
    assert report.is_dry_run is True

    for res in report.models:
        assert isinstance(res, EmbeddingBenchmarkResult)
        assert res.dimension == 768
        assert res.recall_at_1 == 100.0
        assert res.recall_at_5 == 100.0
        assert res.ndcg_at_5 == 1.0
        assert res.memory_kb_per_vector > 0.0
        assert res.overall_score >= 90.0

    # Test markdown and JSON export
    md = bench_runner.generate_markdown(report)
    assert "Leaderboard Summary" in md
    assert "nomic-embed-text" in md

    # Test print_report formats
    bench_runner.print_report(report, format_type="table")
    bench_runner.print_report(report, format_type="json")
    bench_runner.print_report(report, format_type="markdown")


def test_embedding_benchmark_runner_multi_server_dry_run() -> None:
    """Test Cartesian execution across multiple backend servers."""
    bench_runner = EmbeddingBenchmarkRunner(
        models=["nomic-embed-text:latest", "qwen3-embedding:0.6b"],
        servers=["http://hog.lan:11434", "http://workhorse.lan:11434"],
        is_dry_run=True,
    )
    report = bench_runner.run()

    assert len(report.models) == 4  # 2 models * 2 servers
    assert len(report.server_benchmarks) == 2
    assert report.server_benchmarks[0].models_evaluated_count == 2
    assert len(report.recommendations) > 0


def test_embedding_benchmark_runner_mock_engine() -> None:
    """Test benchmark evaluation with mocked EmbeddingsEngine vectors."""
    pairs, corpus = get_embedding_eval_dataset()

    bench_runner = EmbeddingBenchmarkRunner(
        models=["test-embed-model:latest"],
        is_dry_run=False,
    )

    mock_engine = MagicMock()

    def mock_embed_texts(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            val = float(len(t) % 10) + 1.0
            out.append([val / 10.0, 0.5, 0.2, 0.1])
        return out

    mock_engine.embed_texts.side_effect = mock_embed_texts

    with patch.object(bench_runner, "_engine_for_model", return_value=mock_engine):
        result = bench_runner.evaluate_model("test-embed-model:latest", pairs, corpus)
        assert result.model == "test-embed-model:latest"
        assert result.dimension == 4
        assert result.recall_at_1 >= 0.0
        assert result.throughput_items_per_sec > 0.0


def test_document_chunker_and_sampling(tmp_path: Path) -> None:
    """Test InMemoryDocumentTokenizer and load_test_document_corpus."""
    from devops_cli.ai.benchmark.document_chunker import (
        load_test_document_corpus,
    )

    doc_file = tmp_path / "custom_spec.md"
    doc_file.write_text(
        "# Header 1\nSection 1 content with lots of technical details.\n\n"
        "## Subheader 2\nSection 2 describes kubernetes deployments and security contexts.\n\n"
        "### Subheader 3\nSection 3 covers terraform s3 state locking and monitoring.\n",
        encoding="utf-8",
    )

    tasks, corpus, chunks = load_test_document_corpus(
        document_path=doc_file,
        chunk_size_words=20,
        sample_count=2,
    )
    assert len(chunks) >= 3
    assert len(corpus) == len(chunks)
    assert len(tasks) == 2
    for t in tasks:
        assert len(t.query) > 5
        assert t.target_section_index < len(corpus)


def test_cli_benchmark_document_option(tmp_path: Path) -> None:
    """Ensure --document option processes custom document file."""
    doc_file = tmp_path / "test_doc.md"
    doc_file.write_text(
        "# Test Title\nThis is a test document for embedding retrieval.\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["--models", "nomic-embed-text:latest", "--document", str(doc_file), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "test_doc.md" in result.stdout
    assert "Embedding Model Benchmark Suite" in result.stdout


def test_infer_category_exact_word_boundaries_and_domain_classification() -> None:
    """Verify InMemoryDocumentTokenizer._infer_category uses word boundaries
    and domain phrase weighting.
    """
    from devops_cli.ai.benchmark.document_chunker import InMemoryDocumentTokenizer

    # 1. Security domain
    sec_cat = InMemoryDocumentTokenizer._infer_category(
        "Zero-Trust Egress", "Authenticate using OS keyring and prevent SSRF attacks."
    )
    assert sec_cat == "security"

    # 2. Kubernetes domain
    k8s_cat = InMemoryDocumentTokenizer._infer_category(
        "Cluster Pods", "Deploy Traefik IngressRoute with Pod Security Standards."
    )
    assert k8s_cat == "kubernetes"

    # 3. Architecture domain
    arch_cat = InMemoryDocumentTokenizer._infer_category(
        "Python 3.14 AST Engine",
        "Ensure SOLID principles and static typing with Pydantic and mypy.",
    )
    assert arch_cat == "architecture"

    # 4. CI/CD domain (must not trigger on words containing 'pr', 'ci', or 'cd' like 'practice')
    cicd_cat = InMemoryDocumentTokenizer._infer_category(
        "GitHub Actions Workflows", "Run actionlint and pre-commit checks on pull request branch."
    )
    assert cicd_cat == "ci_cd"

    # Word boundary test: "practice" and "prevent" do NOT falsely match PR/CI
    arch_boundary = InMemoryDocumentTokenizer._infer_category(
        "Best Practice Refactoring", "Prevent coupling and increase cohesion."
    )
    assert arch_boundary == "architecture"

    # 5. Infrastructure fallback
    infra_cat = InMemoryDocumentTokenizer._infer_category(
        "OpenTofu State", "Provision S3 backend with DynamoDB locking and Jaeger tracing."
    )
    assert infra_cat == "infrastructure"


def test_embedding_engine_resolution_and_live_eval(tmp_path: Path) -> None:
    """Verify _engine_for_model endpoint resolution and evaluate_model execution with mocked embeddings."""
    from devops_cli.ai.benchmark.embedding_tasks import EmbeddingEvalPair

    runner = EmbeddingBenchmarkRunner(
        models=["custom-model@http://localhost:11434"],
        servers=["http://localhost:11434"],
        is_dry_run=False,
    )
    runner.settings.ai.allow_private_network = True

    # 1. Engine resolution
    engine = runner._engine_for_model("custom-model@http://localhost:11434")
    assert engine.model == "custom-model"

    # 2. evaluate_model with mocked embeddings
    mock_vec = [0.1] * 384
    with (
        patch("devops_cli.ai.rag.embeddings.EmbeddingsEngine.embed_query", return_value=mock_vec),
        patch(
            "devops_cli.ai.rag.embeddings.EmbeddingsEngine.embed_texts",
            return_value=[mock_vec, mock_vec],
        ),
    ):
        pair = EmbeddingEvalPair(
            id="eval-1",
            query="test query",
            target_passage="target passage text for evaluation",
            category="security",
        )

        res = runner.evaluate_model(
            "test-embed",
            [pair],
            ["target passage text for evaluation", "distractor text"],
            server_url="http://localhost:11434",
        )
        assert res.model == "test-embed"
        assert res.dimension == 384
        assert res.recall_at_1 >= 0.0


def test_compute_ndcg_and_report_rendering() -> None:
    """Verify compute_ndcg_at_k with rank outside k and full report print rendering."""
    from devops_cli.ai.benchmark.embedding_runner import compute_ndcg_at_k
    from devops_cli.models.benchmark import EmbeddingServerSummary

    # 1. compute_ndcg_at_k
    assert compute_ndcg_at_k([0, 1, 2], target_idx=0, k=5) == 1.0
    assert compute_ndcg_at_k([1, 2, 3, 4, 5, 0], target_idx=0, k=5) == 0.0

    # 2. EmbeddingBenchmarkRunner.print_report with server summaries and categories
    runner = EmbeddingBenchmarkRunner(models=["m1", "m2"], is_dry_run=True)
    res_1 = EmbeddingBenchmarkResult(
        model="m1",
        server="http://node1:11434",
        dimension=768,
        recall_at_1=90.0,
        recall_at_3=95.0,
        recall_at_5=100.0,
        mrr=0.95,
        ndcg_at_5=0.98,
        mean_cosine_margin=0.45,
        separation_score=0.50,
        latency_ms_p50=12.5,
        latency_ms_p95=25.0,
        throughput_items_per_sec=80.0,
        throughput_chars_per_sec=15000.0,
        overall_score=92.5,
        is_normalized=True,
        category_accuracies={
            "security": 100.0,
            "kubernetes": 85.0,
            "architecture": 90.0,
            "ci_cd": 95.0,
            "infrastructure": 92.0,
        },
        memory_kb_per_vector=3.0,
    )
    res_2 = EmbeddingBenchmarkResult(
        model="m2",
        server="http://node2:11434",
        dimension=384,
        recall_at_1=80.0,
        recall_at_3=90.0,
        recall_at_5=95.0,
        mrr=0.88,
        ndcg_at_5=0.91,
        mean_cosine_margin=0.35,
        separation_score=0.40,
        latency_ms_p50=8.0,
        latency_ms_p95=16.0,
        throughput_items_per_sec=120.0,
        throughput_chars_per_sec=22000.0,
        overall_score=88.0,
        is_normalized=True,
        category_accuracies={"security": 80.0, "kubernetes": 80.0},
        memory_kb_per_vector=1.5,
    )
    srv_1 = EmbeddingServerSummary(
        server="http://node1:11434",
        avg_latency_p50_ms=12.5,
        avg_throughput_items_per_sec=80.0,
        models_evaluated_count=1,
        fastest_model="m1",
        top_score_model="m1",
    )
    srv_2 = EmbeddingServerSummary(
        server="http://node2:11434",
        avg_latency_p50_ms=8.0,
        avg_throughput_items_per_sec=120.0,
        models_evaluated_count=1,
        fastest_model="m2",
        top_score_model="m2",
    )
    rep = EmbeddingBenchmarkReport(
        session_id="20260826-sess",
        models=[res_1, res_2],
        server_benchmarks=[srv_1, srv_2],
        recommendations=["Deploy m1 on node1 for security-critical retrieval."],
        is_dry_run=True,
    )

    runner.print_report(rep, format_type="table")
    md = runner.generate_markdown(rep)
    assert "Server Hardware Comparison" in md
    assert "Key Recommendations" in md
