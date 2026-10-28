"""Unit tests for the embedding model benchmark runner and evaluation metrics."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.benchmark.document_chunker import SectionRetrievalTask
from devops_cli.ai.benchmark.embedding_runner import (
    EmbeddingBenchmarkRunner,
    cosine_similarity,
)
from devops_cli.ai.benchmark.embedding_tasks import (
    get_embedding_eval_dataset,
)
from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.commands.benchmark import app
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.models.benchmark import (
    EmbeddingBenchmarkReport,
    EmbeddingBenchmarkResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.web_fakes import StubWeb

pytestmark = pytest.mark.usefixtures("keyring_store")

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
        servers=["http://example.com:11434", "http://example.com:11435"],
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
        "# Test Title\nThis is a test document for embedding retrieval.\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--models",
            "nomic-embed-text:latest",
            "--document",
            str(doc_file),
            "--dry-run",
        ],
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
        "GitHub Actions Workflows",
        "Run actionlint and pre-commit checks on pull request branch.",
    )
    assert cicd_cat == "ci_cd"

    # Word boundary test: "practice" and "prevent" do NOT falsely match PR/CI
    arch_boundary = InMemoryDocumentTokenizer._infer_category(
        "Best Practice Refactoring", "Prevent coupling and increase cohesion."
    )
    assert arch_boundary == "architecture"

    # 5. Infrastructure fallback
    infra_cat = InMemoryDocumentTokenizer._infer_category(
        "OpenTofu State",
        "Provision S3 backend with DynamoDB locking and Jaeger tracing.",
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
        patch(
            "devops_cli.ai.rag.embeddings.EmbeddingsEngine.embed_query",
            return_value=mock_vec,
        ),
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
        assert (res.model, res.dimension, res.recall_at_1 >= 0.0) == ("test-embed", 384, True)


def test_embedding_engine_provider_resolution() -> None:
    """Verify provider selection for explicit endpoints: origin match or gateway refusal."""
    from devops_cli.exceptions import ValidationError

    runner = EmbeddingBenchmarkRunner(
        models=["m"],
        is_dry_run=False,
    )
    runner.settings.ai.provider = "gateway"
    runner.settings.ai.gateway_url = "https://example.com:4000/v1"
    runner.settings.ai.ollama_urls = ["http://example.com:11434"]
    runner.provider = "gateway"

    with pytest.raises(ValidationError) as exc_info:
        runner._engine_for_model("m@https://example.com:8080")
    assert "--provider" in str(exc_info.value)

    engine_ollama = runner._engine_for_model("m@http://example.com:11434")
    engine_gw = runner._engine_for_model("m@https://example.com:4000/v1")
    assert (engine_ollama.ai_config.provider, engine_gw.ai_config.provider) == (
        "ollama",
        "gateway",
    )

    with pytest.raises(ValidationError):
        runner._engine_for_model("m@https://ollama.example.com")


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
        server="http://example.com:11434",
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
        server="http://example.com:11435",
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
        server="http://example.com:11434",
        avg_latency_p50_ms=12.5,
        avg_throughput_items_per_sec=80.0,
        models_evaluated_count=1,
        fastest_model="m1",
        top_score_model="m1",
    )
    srv_2 = EmbeddingServerSummary(
        server="http://example.com:11435",
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
        recommendations=["Deploy m1 on example.com for security-critical retrieval."],
        is_dry_run=True,
    )

    runner.print_report(rep, format_type="table")
    md = runner.generate_markdown(rep)
    assert "Server Hardware Comparison" in md
    assert "Key Recommendations" in md


@pytest.mark.parametrize(
    ("server", "authorization"),
    [
        ("https://example.com:8443", None),
        ("https://example.com", "Bearer sk-test-configured"),
    ],
)
@pytest.mark.usefixtures("keyring_store")
def test_override_endpoint_gets_no_key(
    monkeypatch: pytest.MonkeyPatch,
    stub_web: StubWeb,
    server: str,
    authorization: str | None,
) -> None:
    """Verify the AI key goes only to the configured api_base_url: an endpoint the model names
    gets no Authorization header, and the engine takes no OPENAI_API_KEY in its place (#954)."""
    monkeypatch.setenv("DEVOPS_CLI_AI_API_KEY", "sk-test-configured")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-environment")
    settings = load_settings()
    settings.ai.api_base_url = "https://example.com/v1"
    bench = EmbeddingBenchmarkRunner(
        models=[f"x@{server}"], settings=settings, provider="openai", is_dry_run=False
    )

    engine = bench._engine_for_model(f"x@{server}")
    with pytest.raises(EmbeddingsError):
        engine.embed_texts(["query"], is_query=True)

    assert [
        (str(sent.url), sent.headers.get("authorization"))
        for sent in stub_web.sent
        if sent.url.host == "example.com"
    ] == [(f"{server}/v1/embeddings", authorization)]


def _canned_vectors(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
    """Distinct, deterministic vectors standing in for a model's embeddings."""
    return [[float(len(text) % 7) + 1.0, 1.0, 0.5] for text in texts]


def _unreachable(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
    """What EmbeddingsEngine raises for a node that refuses the connection."""
    raise EmbeddingsError("Embedding model dead-model failed: ConnectError: connection refused")


def test_unreachable_server_is_reported_failed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify a model whose embeddings fail is reported failed with the reason and no latency,
    ranked after every scored model and left out of the server summary and the recommendations,
    where a p50 of 0.0 made it the lowest-latency model (#954)."""
    pairs, corpus = get_embedding_eval_dataset()
    bench = EmbeddingBenchmarkRunner(
        models=["dead-model", "live-model"],
        servers=["http://localhost:11434"],
        is_dry_run=False,
    )
    engines = {
        "dead-model": MagicMock(embed_texts=MagicMock(side_effect=_unreachable)),
        "live-model": MagicMock(embed_texts=MagicMock(side_effect=_canned_vectors)),
    }
    with (
        patch(
            "devops_cli.ai.benchmark.embedding_runner.load_test_document_corpus",
            return_value=(pairs[:3], corpus, []),
        ),
        patch.object(bench, "_engine_for_model", side_effect=lambda model, _: engines[model]),
    ):
        report = bench.run()

    dead = next(result for result in report.models if result.model == "dead-model")
    assert (
        [result.model for result in report.models],
        (
            dead.failed,
            dead.error,
            dead.latency_ms_p50,
            dead.latency_ms_p95,
            dead.overall_score,
        ),
        [rec for rec in report.recommendations if "dead-model" in rec],
        [(srv.models_evaluated_count, srv.fastest_model) for srv in report.server_benchmarks],
        "✗ dead-model" in capsys.readouterr().out,
    ) == (
        ["live-model", "dead-model"],
        (
            True,
            "Embedding model dead-model failed: ConnectError: connection refused",
            None,
            None,
            0.0,
        ),
        [],
        [(1, "live-model")],
        True,
    )


@pytest.mark.parametrize(
    ("failing_call", "has_latency"),
    [(0, False), (3, True), (4, True)],
    ids=["first-latency-probe", "corpus", "retrieval-queries"],
)
def test_failed_embedding_fails_the_model(failing_call: int, has_latency: bool) -> None:
    """Verify a failure at any embedding call fails the model, sends no request after it, and
    keeps only the latencies of the calls that succeeded (#954)."""
    pairs, corpus = get_embedding_eval_dataset()
    calls: list[int] = []

    def embed(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        calls.append(len(calls))
        if len(calls) - 1 == failing_call:
            raise EmbeddingsError("Embedding model m failed: HTTP 404 model not found")
        return _canned_vectors(texts)

    bench = EmbeddingBenchmarkRunner(models=["m"], is_dry_run=False)
    engine = MagicMock(embed_texts=MagicMock(side_effect=embed))
    with patch.object(bench, "_engine_for_model", return_value=engine):
        result = bench.evaluate_model_on_server("m", "http://localhost:11434", pairs[:3], corpus)

    assert (
        result.failed,
        result.latency_ms_p50 is not None,
        result.recall_at_1,
        result.overall_score,
        len(calls),
    ) == (True, has_latency, 0.0, 0.0, failing_call + 1)


def test_refused_endpoint_is_reported_failed() -> None:
    """Verify a server the engine refuses to reach is a failed result in the report, not a
    model that silently drops out of it (#954)."""
    pairs, corpus = get_embedding_eval_dataset()
    bench = EmbeddingBenchmarkRunner(
        models=["m"], servers=["http://localhost:11434"], is_dry_run=False
    )
    refusal = SSRFBlockedError("http://localhost:11434", reason="private address")
    with (
        patch(
            "devops_cli.ai.benchmark.embedding_runner.load_test_document_corpus",
            return_value=(pairs[:3], corpus, []),
        ),
        patch.object(bench, "_engine_for_model", side_effect=refusal),
    ):
        report = bench.run()

    assert [(result.model, result.failed, result.error) for result in report.models] == [
        ("m", True, refusal.message)
    ]


def test_report_shows_a_failed_run_without_metrics(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify the leaderboards give a failed run no medal and no metrics, and the Markdown report
    says why it failed (#954)."""
    from devops_cli.models.benchmark import EmbeddingServerSummary

    scored = EmbeddingBenchmarkResult(
        model="live-model",
        server="http://localhost:11434",
        dimension=3,
        overall_score=70.0,
    )
    failed = EmbeddingBenchmarkResult(
        model="dead-model",
        server="http://localhost:11435",
        failed=True,
        error="Embedding model dead-model failed: ConnectError",
        is_normalized=False,
    )
    report = EmbeddingBenchmarkReport(
        session_id="20261003-sess",
        models=[scored, failed],
        server_benchmarks=[
            EmbeddingServerSummary(server="http://localhost:11434", models_evaluated_count=1),
            EmbeddingServerSummary(server="http://localhost:11435"),
        ],
    )
    bench = EmbeddingBenchmarkRunner(models=["live-model", "dead-model"], is_dry_run=True)

    bench.print_report(report, format_type="table")
    markdown = bench.generate_markdown(report).splitlines()

    assert (
        [line for line in markdown if "dead-model" in line],
        "✗" in capsys.readouterr().out,
    ) == (
        [
            "| ✗ | `dead-model` | `http://localhost:11435` | - | - | - | - | - | - | - | - | "
            "**failed** |",
            "- `dead-model` on `http://localhost:11435`: "
            "Embedding model dead-model failed: ConnectError",
        ],
        True,
    )


def test_the_category_table_has_a_column_for_each_category_a_run_scored(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify the category table names the categories the results scored, `code` and `iac` for a
    code run, not five documentation domains no code chunk belongs to, with a dash for a model
    that scored none of a category (#481)."""
    scored = {"code": 100.0, "iac": 50.0}
    report = EmbeddingBenchmarkReport(
        session_id="20261022-sess",
        models=[
            EmbeddingBenchmarkResult(
                model="model-a", server="localhost", dimension=3, category_accuracies=scored
            ),
            EmbeddingBenchmarkResult(
                model="model-b", server="localhost", dimension=3, category_accuracies={"code": 80.0}
            ),
        ],
    )

    EmbeddingBenchmarkRunner(models=["model-a"], is_dry_run=True).print_report(report)

    lines = capsys.readouterr().out.splitlines()
    header = next(
        number for number, line in enumerate(lines) if line.split()[:2] == ["Model", "Server"]
    )
    assert [line.split() for line in lines[header : header + 3]] == [
        ["Model", "Server", "code", "iac"],
        ["model-a", "localhost", "100%", "50%"],
        ["model-b", "localhost", "80%", "-"],
    ]


def _source_tree(tmp_path: Path) -> Path:
    """A small tree of source files: two languages with symbols, a script without, and a note."""
    tree = tmp_path / "pkg"
    tree.mkdir()
    (tree / "alpha.py").write_text(
        "def load_config(path):\n"
        "    return path\n"
        "\n"
        "\n"
        "class Store:\n"
        "    def get(self):\n"
        "        return 1\n"
        "\n"
        "    def put(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    (tree / "beta.go").write_text(
        "package main\n\nfunc ServeHTTP() {\n}\n\ntype Router struct {\n}\n", encoding="utf-8"
    )
    (tree / "run.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    (tree / "NOTES.md").write_text("# Notes\nNot code.\n", encoding="utf-8")
    return tree


def _code_task(
    number: int, target: int, location: str, query: str, passage: str, category: str = "code"
) -> SectionRetrievalTask:
    """The retrieval task `load_code_chunk_corpus` builds for the chunk at `location`."""
    return SectionRetrievalTask(
        id=f"code-task-{number}",
        target_section_index=target,
        target_heading=location,
        query=query,
        target_passage=passage,
        category=category,
    )


def test_code_chunks_are_queried_by_their_path_and_symbol_names(tmp_path: Path) -> None:
    """Verify each code chunk with a symbol name becomes a task whose query is its relative path
    and its symbols and whose target is its index in the corpus, while a chunk without a symbol
    stays in the corpus as a distractor and a documentation file is left out of it (#481)."""
    from devops_cli.ai.benchmark.code_chunk_corpus import load_code_chunk_corpus

    tasks, corpus = load_code_chunk_corpus(_source_tree(tmp_path), sample_count=15)

    assert (tasks, corpus) == (
        [
            _code_task(
                1,
                0,
                "alpha.py:1-2",
                "alpha.py load_config",
                "def load_config(path):\n    return path",
            ),
            _code_task(
                2,
                1,
                "alpha.py:5-10",
                "alpha.py Store Store.get Store.put",
                "class Store:\n"
                "    def get(self):\n"
                "        return 1\n"
                "\n"
                "    def put(self):\n"
                "        return 2",
            ),
            _code_task(3, 2, "beta.go:3-4", "beta.go ServeHTTP", "func ServeHTTP() {\n}"),
            _code_task(4, 3, "beta.go:6-7", "beta.go Router", "type Router struct {\n}"),
        ],
        [
            "def load_config(path):\n    return path",
            "class Store:\n"
            "    def get(self):\n"
            "        return 1\n"
            "\n"
            "    def put(self):\n"
            "        return 2",
            "func ServeHTTP() {\n}",
            "type Router struct {\n}",
            "#!/bin/sh\necho hi",
        ],
    )


def test_code_tasks_are_sampled_evenly_across_the_chunks(tmp_path: Path) -> None:
    """Verify a sample smaller than the code chunks takes evenly spaced ones, the same every run,
    each still targeting its own index in the whole corpus (#481)."""
    from devops_cli.ai.benchmark.code_chunk_corpus import load_code_chunk_corpus

    (tmp_path / "many.py").write_text(
        "".join(f"def fn_{name}():\n    return 1\n" for name in "abcdef"), encoding="utf-8"
    )

    tasks, corpus = load_code_chunk_corpus(tmp_path, sample_count=3)

    assert ([(task.target_section_index, task.query) for task in tasks], len(corpus)) == (
        [(0, "many.py fn_a"), (2, "many.py fn_c"), (4, "many.py fn_e")],
        6,
    )


def test_a_query_that_names_two_chunks_has_no_single_target(tmp_path: Path) -> None:
    """Verify two chunks sharing a path and symbols, as a redefined function does, get no task,
    since the query would have two right answers, while both stay in the corpus (#481)."""
    from devops_cli.ai.benchmark.code_chunk_corpus import load_code_chunk_corpus

    (tmp_path / "dup.py").write_text(
        "def handler():\n    return 1\n\ndef handler():\n    return 2\n\ndef unique():\n    return 3\n",
        encoding="utf-8",
    )

    tasks, corpus = load_code_chunk_corpus(tmp_path, sample_count=15)

    assert ([(task.target_section_index, task.query) for task in tasks], len(corpus)) == (
        [(2, "dup.py unique")],
        3,
    )


def test_a_class_is_queried_by_its_first_symbols_as_the_index_lookup_is(tmp_path: Path) -> None:
    """Verify a class with many methods is queried by its first five symbols, the lookup
    `outlines` makes for a file, not by every method (#481)."""
    from devops_cli.ai.benchmark.code_chunk_corpus import load_code_chunk_corpus

    methods = "".join(f"    def m{number}(self):\n        return {number}\n" for number in range(7))
    (tmp_path / "big.py").write_text(f"class Big:\n{methods}", encoding="utf-8")

    tasks, _ = load_code_chunk_corpus(tmp_path, sample_count=15)

    assert [task.query for task in tasks] == ["big.py Big Big.m0 Big.m1 Big.m2 Big.m3"]


def test_a_files_preamble_is_a_distractor_not_a_target(tmp_path: Path) -> None:
    """Verify the chunk of a Python file's imports and docstring, whose only symbol is the
    chunker's module marker and whose content names no path, stays in the corpus without a task,
    since a query of its path and the marker has nothing in it to find the chunk by (#481)."""
    from devops_cli.ai.benchmark.code_chunk_corpus import load_code_chunk_corpus

    (tmp_path / "service.py").write_text(
        '"""Serve."""\nimport os\n\n\ndef serve():\n    return os.name\n', encoding="utf-8"
    )

    tasks, corpus = load_code_chunk_corpus(tmp_path, sample_count=15)

    assert ([(task.target_section_index, task.query) for task in tasks], corpus) == (
        [(1, "service.py serve")],
        ['"""Serve."""\nimport os', "def serve():\n    return os.name"],
    )


def test_a_code_query_and_the_index_lookup_carry_the_same_symbols() -> None:
    """Verify the query the benchmark makes for a chunk is the lookup `outlines` makes for the
    file, a path and the same first symbols, so the two cannot drift apart (#481)."""
    from devops_cli.ai.analyze.outlines import _enhance_file_metadata_with_ai
    from devops_cli.ai.benchmark.code_chunk_corpus import _code_chunk_query
    from devops_cli.ai.rag.models import CodeChunk

    symbols = [f"Big.m{number}" for number in range(9)]
    lookups: list[str] = []

    def record(query: str, **_: Any) -> MagicMock:
        lookups.append(query)
        return MagicMock()

    with (
        patch("devops_cli.ai.rag.investigator.investigate_rag_context", side_effect=record),
        patch("devops_cli.ai.rag.investigator.format_rag_investigation_for_prompt"),
    ):
        _enhance_file_metadata_with_ai(
            "pkg/big.py", "class Big: pass", "python", symbols, MagicMock()
        )
    chunk = CodeChunk(
        id="big",
        file_path="pkg/big.py",
        start_line=1,
        end_line=2,
        content="class Big: pass",
        symbol_names=symbols,
    )

    assert lookups == [_code_chunk_query(chunk)]


def test_a_directory_with_no_symbol_to_query_by_is_refused(tmp_path: Path) -> None:
    """Verify a directory whose code chunks name no symbol is refused with the directory named,
    not benchmarked over an empty task list that scores every model 0% (#481)."""
    from devops_cli.ai.benchmark.code_chunk_corpus import load_code_chunk_corpus
    from devops_cli.exceptions import ValidationError

    tree = _source_tree(tmp_path)
    (tree / "alpha.py").unlink()
    (tree / "beta.go").unlink()

    with pytest.raises(ValidationError) as raised:
        load_code_chunk_corpus(tree, sample_count=15)

    assert (raised.value.exit_code, raised.value.error_code, raised.value.message) == (
        1,
        "VALIDATION_ERROR",
        f"No code chunk under '{tree.resolve()}' has a symbol name to query by, so the benchmark "
        "has nothing to retrieve: point --code at a directory of source files.",
    )


@pytest.fixture
def lexical_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer each Ollama embedding request with vectors that place a text on the symbols of
    `_source_tree` it names, so a text finds the chunk that defines the symbols it mentions."""
    import re

    symbols = ["load_config", "Store", "ServeHTTP", "Router"]

    def embed(text: str) -> list[float]:
        words = set(re.findall(r"[A-Za-z_]+", text))
        return [*(1.0 if symbol in words else 0.0 for symbol in symbols), 0.1]

    def answer(_client: httpx2.Client, url: str, **kwargs: Any) -> httpx2.Response:
        vectors = [embed(text) for text in kwargs["json"]["input"]]
        return httpx2.Response(
            200, json={"embeddings": vectors}, request=httpx2.Request("POST", url)
        )

    monkeypatch.setattr(httpx2.Client, "post", answer)


@pytest.mark.usefixtures("lexical_embeddings")
def test_a_model_that_finds_each_code_chunk_by_its_symbols_scores_full_recall(
    tmp_path: Path,
) -> None:
    """Verify a code run ranks the chunks the queries came from: an embedder that places a text
    on the symbols it names finds every target first, so recall@1, MRR and nDCG are all 1 (#481)."""
    bench = EmbeddingBenchmarkRunner(
        models=["lexical-embed"],
        servers=["http://localhost:11434"],
        is_dry_run=False,
        code_path=_source_tree(tmp_path),
    )
    bench.settings.ai.allow_private_network = True

    report = bench.run()

    assert [
        (
            result.model,
            result.failed,
            result.dimension,
            result.recall_at_1,
            result.recall_at_5,
            result.mrr,
            result.ndcg_at_5,
        )
        for result in report.models
    ] == [("lexical-embed", False, 5, 100.0, 100.0, 1.0, 1.0)]


def test_the_code_digest_follows_the_files_not_the_spelling_of_the_directory(
    tmp_path: Path,
) -> None:
    """Verify the digest a code run is recorded under is the same for a directory spelled two
    ways and for a copy of it elsewhere, and differs once a file in it changes (#481)."""
    import shutil

    from devops_cli.ai.benchmark.code_chunk_corpus import code_tree_digest

    tree = _source_tree(tmp_path)
    copy = shutil.copytree(tree, tmp_path / "copy" / "pkg")
    before = code_tree_digest(tree)
    (tree / "alpha.py").write_text("def load_config(path):\n    return None\n", encoding="utf-8")

    assert (
        code_tree_digest(copy),
        code_tree_digest(tree / ".." / "pkg") != before,
        code_tree_digest(copy / ".." / "pkg"),
    ) == (before, True, before)


@pytest.mark.usefixtures("lexical_embeddings")
def test_a_code_run_is_recorded_with_the_files_it_ranked(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify a recorded code run names the digest of the files its corpus is drawn from in its
    subject, beside the document it does not use, so a baseline from before a source change is
    not compared with a run after it (#481)."""
    from devops_cli.ai.run_store import Mechanism, load_runs

    tree = _source_tree(tmp_path)

    result = cli(
        "ai",
        "benchmark",
        "--type",
        "embedding",
        "--models",
        "lexical-embed",
        "--servers",
        "http://localhost:11434",
        "--code",
        tree,
        env={"DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "true"},
    )
    (recorded,) = load_runs(Mechanism.AI_BENCHMARK)

    assert (result.exit_code, recorded.subject) == (
        0,
        {"kind": "embedding", "document": None, "code": "924c82ce9f27350f", "samples": 5},
    )


def test_the_code_option_ranks_the_code_chunks_of_a_directory(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify `devops ai benchmark --code <dir>` benchmarks the directory's code chunks in place
    of the document sections, naming the directory and its chunk count (#481)."""
    result = cli(
        "ai",
        "benchmark",
        "--type",
        "embedding",
        "--models",
        "lexical-embed",
        "--code",
        _source_tree(tmp_path),
        "--dry-run",
    )

    assert (result.exit_code, "Code: pkg (5 chunks)" in result.output) == (0, True)


def test_a_code_option_of_dot_names_the_directory_it_stands_in(
    tmp_path: Path, cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `--code .` names the directory it resolves to in the report's header, not an empty
    name, since `.` is how a run from the repository root reads the paths the index stores (#481)."""
    monkeypatch.chdir(_source_tree(tmp_path))

    result = cli(
        "ai",
        "benchmark",
        "--type",
        "embedding",
        "--models",
        "lexical-embed",
        "--code",
        ".",
        "--dry-run",
    )

    assert (result.exit_code, "Code: pkg (5 chunks)" in result.output) == (0, True)


def test_a_code_directory_with_nothing_to_query_by_is_the_commands_error(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify `--code` of a directory whose chunks name no symbol exits 1 with the message that
    names the directory, and runs no benchmark (#481)."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")

    result = cli(
        "ai",
        "benchmark",
        "--type",
        "embedding",
        "--models",
        "lexical-embed",
        "--code",
        scripts,
        "--dry-run",
    )

    assert (
        result.exit_code,
        "point --code at a directory of source files" in result.output,
        "Benchmark Suite" in result.output,
    ) == (1, True, False)


def test_the_code_and_document_options_are_not_taken_together(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify `--code` and `--document` together are refused, each choosing the corpus the
    benchmark ranks, and no benchmark runs (#481)."""
    document = tmp_path / "spec.md"
    document.write_text("# Spec\nA document.\n", encoding="utf-8")

    result = cli(
        "ai",
        "benchmark",
        "--type",
        "embedding",
        "--code",
        _source_tree(tmp_path),
        "--document",
        document,
        "--dry-run",
    )

    assert (result.exit_code, "pass one" in result.output, "Benchmark Suite" in result.output) == (
        1,
        True,
        False,
    )


def test_the_embedding_benchmark_defaults_to_the_two_candidate_models() -> None:
    """Verify a runner given no models benchmarks the two models that #481 compared:
    `bge-m3:latest` and `qwen3-embedding:0.6b` (#481)."""
    assert EmbeddingBenchmarkRunner(is_dry_run=True).models == [
        "bge-m3:latest",
        "qwen3-embedding:0.6b",
    ]


def test_an_endpoint_that_ollama_urls_cannot_hold_fails_the_run_of_that_model() -> None:
    """Verify a `model@endpoint` whose URL is not http or https fails the run of that model.

    The engine's clients check the address at the connect (#2422), so the endpoint is checked
    only as `ai.ollama_urls` checks a URL. The error fails the run of that model, with its reason,
    instead of the whole benchmark.
    """
    bench = EmbeddingBenchmarkRunner(models=["m"], provider="ollama", is_dry_run=False)

    result = bench.evaluate_model("m@ftp://example.com:21", [], ["probe"])

    assert (
        result.failed,
        "Embedding benchmark endpoint 'ftp://example.com:21' cannot be used"
        in (result.error or ""),
    ) == (True, True)
