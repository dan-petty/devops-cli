"""Benchmarking engine for evaluating vector embeddings, latency, throughput, and retrieval."""

from __future__ import annotations

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.benchmark.document_chunker import (
    SectionRetrievalTask,
    load_test_document_corpus,
)
from devops_cli.ai.benchmark.embedding_tasks import (
    EmbeddingEvalPair,
)
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.constants import (
    CONST_BENCHMARKS_DATA_DIR,
    CONST_EMBEDDING_REPORT_FILENAME,
    CONST_FP32_BYTES_PER_ELEMENT,
    CONST_KILOBYTE_BYTES,
)
from devops_cli.config.defaults import (
    DEFAULT_DRY_RUN_EMBEDDING_CATEGORIES,
    DEFAULT_DRY_RUN_EMBEDDING_DIMENSION,
    DEFAULT_DRY_RUN_EMBEDDING_LATENCY_P50,
    DEFAULT_DRY_RUN_EMBEDDING_LATENCY_P95,
    DEFAULT_DRY_RUN_EMBEDDING_MARGIN,
    DEFAULT_DRY_RUN_EMBEDDING_MRR,
    DEFAULT_DRY_RUN_EMBEDDING_NDCG,
    DEFAULT_DRY_RUN_EMBEDDING_OVERALL_SCORE,
    DEFAULT_DRY_RUN_EMBEDDING_RECALL,
    DEFAULT_DRY_RUN_EMBEDDING_SEPARATION,
    DEFAULT_DRY_RUN_EMBEDDING_THROUGHPUT_CHARS,
    DEFAULT_DRY_RUN_EMBEDDING_THROUGHPUT_ITEMS,
    DEFAULT_EMBEDDING_BENCHMARK_CONCURRENCY,
    DEFAULT_EMBEDDING_BENCHMARK_MODELS,
    DEFAULT_EMBEDDING_BENCHMARK_SAMPLE_COUNT,
)
from devops_cli.config.settings import AIConfig, Settings, get_ai_api_key, load_settings
from devops_cli.models.benchmark import (
    EmbeddingBenchmarkReport,
    EmbeddingBenchmarkResult,
    EmbeddingServerSummary,
)
from devops_cli.output import (
    print_info,
    print_markdown,
    print_panel,
    print_table,
    write_stdout,
)

logger = logging.getLogger(__name__)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def compute_ndcg_at_k(ranked_indices: list[int], target_idx: int, k: int = 5) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank K for binary relevance."""
    for rank_idx, doc_idx in enumerate(ranked_indices[:k], 1):
        if doc_idx == target_idx:
            dcg = 1.0 / math.log2(rank_idx + 1)
            idcg = 1.0 / math.log2(1 + 1)
            return float(dcg / idcg)
    return 0.0


class EmbeddingBenchmarkRunner:
    """Orchestrates comprehensive multi-model, multi-server vector embedding benchmarks."""

    def __init__(
        self,
        models: list[str] | None = None,
        settings: Settings | None = None,
        provider: str | None = None,
        is_dry_run: bool | None = None,
        concurrency: int = DEFAULT_EMBEDDING_BENCHMARK_CONCURRENCY,
        servers: list[str] | None = None,
        document_path: Path | None = None,
        sample_count: int = DEFAULT_EMBEDDING_BENCHMARK_SAMPLE_COUNT,
    ) -> None:
        self.models = models or list(DEFAULT_EMBEDDING_BENCHMARK_MODELS)
        self.settings = settings or load_settings()
        self.provider = provider or self.settings.ai.provider
        self.session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._is_dry_run_override = is_dry_run
        self.servers = servers or self.settings.ai.ollama_urls or ["http://localhost:11434"]
        self.concurrency = max(1, concurrency)
        self.document_path = document_path
        self.sample_count = sample_count
        self._print_lock = threading.Lock()

    @property
    def is_dry_run_active(self) -> bool:
        if self._is_dry_run_override is not None:
            return self._is_dry_run_override
        from devops_cli.dry_run.state import is_dry_run

        return is_dry_run()

    def _engine_for_model(self, model_name: str, server_url: str | None = None) -> EmbeddingsEngine:
        """Instantiate an EmbeddingsEngine configured for the specified model and server."""
        from devops_cli.core.validation import validate_url

        endpoint = server_url
        clean_model = model_name
        if "@" in model_name:
            clean_model, _, explicit_endpoint = model_name.partition("@")
            if explicit_endpoint:
                endpoint = explicit_endpoint

        if not endpoint and self.servers:
            endpoint = self.servers[0]

        resolved_provider = self.provider
        if endpoint and (":11434" in endpoint or "ollama" in endpoint):
            resolved_provider = "ollama"

        allow_priv = self.settings.ai.allow_private_network
        ai_kwargs: dict[str, Any] = {
            "provider": resolved_provider,
            "allow_private_network": allow_priv,
            "rag": {"embedding_model": clean_model},
        }

        if endpoint:
            clean_endpoint = validate_url(endpoint, "benchmark server", allow_private=allow_priv)
            ai_kwargs["ollama_urls"] = [clean_endpoint]
            ai_kwargs["api_base_url"] = clean_endpoint

        cfg = AIConfig(**ai_kwargs)
        api_key = get_ai_api_key(self.settings)
        return EmbeddingsEngine(cfg, api_key=api_key)

    def evaluate_model(
        self,
        model_name: str,
        pairs: list[SectionRetrievalTask] | list[EmbeddingEvalPair],
        corpus: list[str],
        server_url: str | None = None,
    ) -> EmbeddingBenchmarkResult:
        """Execute full benchmark evaluation for a single model."""
        endpoint = server_url
        if "@" in model_name:
            clean_model, _, explicit_endpoint = model_name.partition("@")
            if explicit_endpoint:
                endpoint = explicit_endpoint
        if not endpoint:
            endpoint = self.servers[0] if self.servers else "default"
        return self.evaluate_model_on_server(model_name, endpoint, pairs, corpus)

    def evaluate_model_on_server(
        self,
        model_name: str,
        server_url: str,
        pairs: list[SectionRetrievalTask] | list[EmbeddingEvalPair],
        corpus: list[str],
    ) -> EmbeddingBenchmarkResult:
        """Execute full benchmark evaluation for a single model on a specific server."""
        clean_model = model_name.split("@")[0]

        with self._print_lock:
            print_info(
                f"[bold cyan]⏳ Benchmarking:[/bold cyan] {clean_model} "
                f"[dim]on {server_url}[/dim]...",
                prefix=False,
            )

        if self.is_dry_run_active:
            dim = DEFAULT_DRY_RUN_EMBEDDING_DIMENSION
            return EmbeddingBenchmarkResult(
                model=clean_model,
                server=server_url,
                dimension=dim,
                recall_at_1=DEFAULT_DRY_RUN_EMBEDDING_RECALL,
                recall_at_3=DEFAULT_DRY_RUN_EMBEDDING_RECALL,
                recall_at_5=DEFAULT_DRY_RUN_EMBEDDING_RECALL,
                mrr=DEFAULT_DRY_RUN_EMBEDDING_MRR,
                ndcg_at_5=DEFAULT_DRY_RUN_EMBEDDING_NDCG,
                mean_cosine_margin=DEFAULT_DRY_RUN_EMBEDDING_MARGIN,
                separation_score=DEFAULT_DRY_RUN_EMBEDDING_SEPARATION,
                latency_ms_p50=DEFAULT_DRY_RUN_EMBEDDING_LATENCY_P50,
                latency_ms_p95=DEFAULT_DRY_RUN_EMBEDDING_LATENCY_P95,
                throughput_items_per_sec=DEFAULT_DRY_RUN_EMBEDDING_THROUGHPUT_ITEMS,
                throughput_chars_per_sec=DEFAULT_DRY_RUN_EMBEDDING_THROUGHPUT_CHARS,
                overall_score=DEFAULT_DRY_RUN_EMBEDDING_OVERALL_SCORE,
                is_normalized=True,
                category_accuracies={
                    cat: DEFAULT_DRY_RUN_EMBEDDING_RECALL
                    for cat in DEFAULT_DRY_RUN_EMBEDDING_CATEGORIES
                },
                memory_kb_per_vector=round(
                    (dim * CONST_FP32_BYTES_PER_ELEMENT) / CONST_KILOBYTE_BYTES, 2
                ),
            )

        engine = self._engine_for_model(clean_model, server_url)

        # 1. Measure single-query latencies (p50, p95)
        query_latencies: list[float] = []
        for pair in pairs[:5]:
            t0 = time.perf_counter()
            try:
                engine.embed_texts([pair.query], is_query=True)
                dur_ms = (time.perf_counter() - t0) * 1000.0
                query_latencies.append(dur_ms)
            except Exception as exc:
                logger.warning(
                    "Query embedding failed for %s on %s: %s", clean_model, server_url, exc
                )

        query_latencies.sort()
        p50_lat = query_latencies[len(query_latencies) // 2] if query_latencies else 0.0
        p95_lat = query_latencies[int(len(query_latencies) * 0.95)] if query_latencies else 0.0

        # 2. Measure batch throughput across complete corpus
        total_chars = sum(len(doc) for doc in corpus)
        t_batch_start = time.perf_counter()
        try:
            corpus_vectors = engine.embed_texts(corpus, is_query=False)
            batch_dur = max(time.perf_counter() - t_batch_start, 0.001)
            items_per_sec = len(corpus) / batch_dur
            chars_per_sec = total_chars / batch_dur
        except Exception as exc:
            logger.error("Corpus embedding failed for %s on %s: %s", clean_model, server_url, exc)
            corpus_vectors = []
            items_per_sec = 0.0
            chars_per_sec = 0.0

        # 3. Vector health and dimension checks
        dimension = len(corpus_vectors[0]) if corpus_vectors and corpus_vectors[0] else 0
        is_normalized = True
        if corpus_vectors and corpus_vectors[0]:
            norm = math.sqrt(sum(x * x for x in corpus_vectors[0]))
            is_normalized = abs(norm - 1.0) < 0.05 or abs(norm - 0.0) < 0.01

        # 4. Embed queries for retrieval evaluation
        query_texts = [p.query for p in pairs]
        try:
            query_vectors = engine.embed_texts(query_texts, is_query=True)
        except Exception as exc:
            logger.error("Query embeddings failed for %s on %s: %s", clean_model, server_url, exc)
            query_vectors = []

        # 5. Compute semantic retrieval metrics (Recall@1, Recall@3, Recall@5, MRR, NDCG@5, Margin)
        top1_hits = 0
        top3_hits = 0
        top5_hits = 0
        reciprocal_ranks: list[float] = []
        ndcg_scores: list[float] = []
        margins: list[float] = []
        target_sims: list[float] = []
        distractor_sims: list[float] = []
        category_hits: dict[str, list[int]] = {}

        has_all_queries = query_vectors and len(query_vectors) == len(pairs)
        has_all_corpus = corpus_vectors and len(corpus_vectors) == len(corpus)

        if has_all_queries and has_all_corpus:
            for idx, (eval_item, q_vec) in enumerate(zip(pairs, query_vectors, strict=False)):
                cat = getattr(eval_item, "category", "general")
                category_hits.setdefault(cat, [])

                scored_passages: list[tuple[int, float]] = []
                for c_idx, c_vec in enumerate(corpus_vectors):
                    sim = cosine_similarity(q_vec, c_vec)
                    scored_passages.append((c_idx, sim))

                scored_passages.sort(key=lambda x: x[1], reverse=True)
                ranked_indices = [idx_and_sim[0] for idx_and_sim in scored_passages]

                target_idx = getattr(eval_item, "target_section_index", idx)

                if target_idx in ranked_indices:
                    rank = ranked_indices.index(target_idx) + 1
                else:
                    rank = len(corpus)

                rr = 1.0 / rank
                reciprocal_ranks.append(rr)

                # Compute NDCG@5
                ndcg = compute_ndcg_at_k(ranked_indices, target_idx, k=5)
                ndcg_scores.append(ndcg)

                # Target similarity vs best distractor
                t_sim = next((sim for c_i, sim in scored_passages if c_i == target_idx), 0.0)
                target_sims.append(t_sim)

                other_sims = [sim for c_i, sim in scored_passages if c_i != target_idx]
                best_other_sim = max(other_sims) if other_sims else 0.0
                distractor_sims.extend(other_sims)
                margins.append(t_sim - best_other_sim)

                if rank == 1:
                    top1_hits += 1
                    category_hits[cat].append(1)
                else:
                    category_hits[cat].append(0)

                if rank <= 3:
                    top3_hits += 1
                if rank <= 5:
                    top5_hits += 1

        total_pairs = max(len(pairs), 1)
        recall_1 = (top1_hits / total_pairs) * 100.0
        recall_3 = (top3_hits / total_pairs) * 100.0
        recall_5 = (top5_hits / total_pairs) * 100.0
        mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
        ndcg_5 = (sum(ndcg_scores) / len(ndcg_scores)) if ndcg_scores else 0.0
        mean_margin = (sum(margins) / len(margins)) if margins else 0.0

        mean_t_sim = sum(target_sims) / len(target_sims) if target_sims else 0.0
        mean_d_sim = sum(distractor_sims) / len(distractor_sims) if distractor_sims else 0.0
        separation = mean_t_sim - mean_d_sim

        cat_accs = {
            cat: (sum(hits) / len(hits) * 100.0) if hits else 0.0
            for cat, hits in category_hits.items()
        }

        # Overall Score Calculation: 60% Retrieval Quality, 30% Throughput/Latency, 10% Health
        quality_score = (
            (recall_1 * 0.35)
            + (ndcg_5 * 100.0 * 0.35)
            + (mrr * 100.0 * 0.15)
            + (max(0.0, mean_margin * 100.0) * 0.15)
        )
        perf_score = min(100.0, (items_per_sec / 50.0) * 50.0 + max(0.0, (100.0 - p50_lat / 10.0)))
        health_score = 100.0 if (dimension > 0 and is_normalized) else 50.0
        overall = (quality_score * 0.6) + (perf_score * 0.3) + (health_score * 0.1)

        mem_kb = round((dimension * 4) / 1024, 2)

        with self._print_lock:
            print_info(
                f"  [bold green]✓[/bold green] {clean_model} on {server_url} | "
                f"dim={dimension} | R@1={recall_1:.0f}% | MRR={mrr:.2f} | "
                f"p50={p50_lat:.1f}ms | {items_per_sec:.1f} items/s → [bold]{overall:.1f}%[/bold]",
                prefix=False,
            )

        return EmbeddingBenchmarkResult(
            model=clean_model,
            server=server_url,
            dimension=dimension,
            recall_at_1=round(recall_1, 2),
            recall_at_3=round(recall_3, 2),
            recall_at_5=round(recall_5, 2),
            mrr=round(mrr, 3),
            ndcg_at_5=round(ndcg_5, 3),
            mean_cosine_margin=round(mean_margin, 3),
            separation_score=round(separation, 3),
            latency_ms_p50=round(p50_lat, 2),
            latency_ms_p95=round(p95_lat, 2),
            throughput_items_per_sec=round(items_per_sec, 2),
            throughput_chars_per_sec=round(chars_per_sec, 2),
            overall_score=round(overall, 2),
            is_normalized=is_normalized,
            category_accuracies=cat_accs,
            memory_kb_per_vector=mem_kb,
        )

    def run(self) -> EmbeddingBenchmarkReport:
        """Execute parallel benchmark across all candidate embedding models and servers."""
        # Load large test document, tokenize in memory, and extract section evaluation tasks
        eval_tasks, corpus, chunks = load_test_document_corpus(
            document_path=self.document_path,
            repo_root=Path.cwd(),
            sample_count=self.sample_count,
        )

        # Build Cartesian product of (model, server) if multiple servers provided
        target_runs: list[tuple[str, str]] = []
        for m in self.models:
            if "@" in m:
                clean_m, _, srv = m.partition("@")
                target_runs.append((clean_m, srv))
            elif len(self.servers) > 1:
                for srv in self.servers:
                    target_runs.append((m, srv))
            else:
                srv = self.servers[0] if self.servers else "default"
                target_runs.append((m, srv))

        doc_source = (
            self.document_path.name if self.document_path else "AGENTS.md & Workspace Specs"
        )
        total_words = sum(c.token_count for c in chunks)
        print_info("\n[bold]⚡ DevOps CLI Embedding Model Benchmark Suite[/bold]", prefix=False)
        print_info(
            f"[dim]Session: {self.session_id} | Document: {doc_source} "
            f"({len(chunks)} chunks, ~{total_words} words) | "
            f"Evaluation Sections: {len(eval_tasks)} | Models: {len(self.models)} | "
            f"Servers: {len(self.servers)} | Total Executions: {len(target_runs)}[/dim]\n",
            prefix=False,
        )

        results: list[EmbeddingBenchmarkResult] = []
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(target_runs))) as executor:
            future_to_run = {
                executor.submit(self.evaluate_model_on_server, m, srv, eval_tasks, corpus): (m, srv)
                for m, srv in target_runs
            }
            for future in as_completed(future_to_run):
                m_name, srv_name = future_to_run[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    logger.error("Evaluation failed for model %s on %s: %s", m_name, srv_name, exc)

        results.sort(key=lambda r: r.overall_score, reverse=True)

        # Compute Server Performance Summaries
        server_summaries: list[EmbeddingServerSummary] = []
        server_map: dict[str, list[EmbeddingBenchmarkResult]] = {}
        for r in results:
            server_map.setdefault(r.server, []).append(r)

        for srv, srv_results in server_map.items():
            avg_lat = sum(r.latency_ms_p50 for r in srv_results) / len(srv_results)
            avg_tp = sum(r.throughput_items_per_sec for r in srv_results) / len(srv_results)
            fastest = min(srv_results, key=lambda r: r.latency_ms_p50).model if srv_results else ""
            top_model = max(srv_results, key=lambda r: r.overall_score).model if srv_results else ""
            server_summaries.append(
                EmbeddingServerSummary(
                    server=srv,
                    avg_latency_p50_ms=round(avg_lat, 2),
                    avg_throughput_items_per_sec=round(avg_tp, 2),
                    models_evaluated_count=len(srv_results),
                    fastest_model=fastest,
                    top_score_model=top_model,
                )
            )

        # Synthesize actionable architectural recommendations
        recommendations: list[str] = []
        if results:
            best_overall = results[0]
            recommendations.append(
                f"Top Overall Model: '{best_overall.model}' "
                f"({best_overall.overall_score:.1f}% overall, "
                f"Recall@1={best_overall.recall_at_1:.0f}%, "
                f"MRR={best_overall.mrr:.2f}) on {best_overall.server}."
            )

            fastest_model = min(results, key=lambda r: r.latency_ms_p50)
            recommendations.append(
                f"Lowest Latency: '{fastest_model.model}' with "
                f"{fastest_model.latency_ms_p50:.1f}ms p50 latency on {fastest_model.server} "
                "(ideal for per-turn conversational retrieval)."
            )

            highest_tp = max(results, key=lambda r: r.throughput_items_per_sec)
            recommendations.append(
                f"Highest Indexing Throughput: '{highest_tp.model}' with "
                f"{highest_tp.throughput_items_per_sec:.1f} items/sec on {highest_tp.server} "
                "(recommended for large multi-repo indexing)."
            )

            compact_model = min(results, key=lambda r: r.dimension)
            mem_kb = compact_model.memory_kb_per_vector
            recommendations.append(
                f"Memory Efficiency: '{compact_model.model}' "
                f"({compact_model.dimension} dim / {mem_kb:.1f} KB/vec, "
                f"~{mem_kb:.1f} GB per 1M vectors in Qdrant)."
            )

        report = EmbeddingBenchmarkReport(
            session_id=self.session_id,
            models=results,
            server_benchmarks=server_summaries,
            recommendations=recommendations,
            is_dry_run=self.is_dry_run_active,
        )

        self._save_report(report)
        return report

    def _save_report(self, report: EmbeddingBenchmarkReport) -> None:
        """Save benchmark report to disk under .data/benchmarks/<session_id>/."""
        bench_dir = CONST_BENCHMARKS_DATA_DIR / self.session_id
        bench_dir.mkdir(parents=True, exist_ok=True)
        report_file = bench_dir / CONST_EMBEDDING_REPORT_FILENAME
        report_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved embedding benchmark report to %s", report_file)

    def print_report(self, report: EmbeddingBenchmarkReport, format_type: str = "table") -> None:
        """Render the comprehensive benchmark report in the requested format."""
        if format_type.lower() == "json":
            write_stdout(report.model_dump_json(indent=2) + "\n")
            return

        if format_type.lower() == "markdown":
            md = self.generate_markdown(report)
            print_markdown(md)
            return

        # 1. Overall Leaderboard Table
        columns = [
            ("Rank", "dim"),
            ("Model", "bold cyan"),
            ("Server", "dim"),
            "Dim",
            ("Recall@1", "green"),
            "Recall@3",
            "MRR",
            "NDCG@5",
            "Margin",
            "p50 (ms)",
            ("Items/s", "yellow"),
            ("Score", "bold magenta"),
        ]
        rows: list[list[str]] = []
        for rank, res in enumerate(report.models, 1):
            if rank == 1:
                badge = "🥇"
            elif rank == 2:
                badge = "🥈"
            elif rank == 3:
                badge = "🥉"
            else:
                badge = f"#{rank}"

            rows.append(
                [
                    badge,
                    res.model,
                    res.server,
                    str(res.dimension),
                    f"{res.recall_at_1:.1f}%",
                    f"{res.recall_at_3:.1f}%",
                    f"{res.mrr:.3f}",
                    f"{res.ndcg_at_5:.3f}",
                    f"{res.mean_cosine_margin:+.3f}",
                    f"{res.latency_ms_p50:.1f}",
                    f"{res.throughput_items_per_sec:.1f}",
                    f"{res.overall_score:.1f}%",
                ]
            )

        print_table(
            title=f"⚡ Embedding Model Benchmark Leaderboard — {report.session_id}",
            columns=columns,
            rows=rows,
        )

        # 2. Domain Breakdown Table
        if report.models and any(r.category_accuracies for r in report.models):
            cat_cols = [
                ("Model", "bold"),
                ("Server", "dim"),
                "Security",
                "Kubernetes",
                "Architecture",
                "CI/CD",
                "Infrastructure",
            ]
            cat_rows: list[list[str]] = []
            for res in report.models:
                cats = res.category_accuracies
                cat_rows.append(
                    [
                        res.model,
                        res.server,
                        f"{cats['security']:.0f}%" if "security" in cats else "-",
                        f"{cats['kubernetes']:.0f}%" if "kubernetes" in cats else "-",
                        f"{cats['architecture']:.0f}%" if "architecture" in cats else "-",
                        f"{cats['ci_cd']:.0f}%" if "ci_cd" in cats else "-",
                        f"{cats['infrastructure']:.0f}%" if "infrastructure" in cats else "-",
                    ]
                )
            write_stdout("\n")
            print_table(
                title="📂 Category & Domain Retrieval Accuracy (%)",
                columns=cat_cols,
                rows=cat_rows,
            )

        # 3. Server Performance Comparison (if multiple servers evaluated)
        if len(report.server_benchmarks) > 1:
            srv_cols = [
                ("Server Endpoint", "bold"),
                "Models Evaluated",
                "Avg Latency (p50)",
                "Avg Throughput",
                ("Fastest Model", "cyan"),
                ("Top Scoring Model", "magenta"),
            ]
            srv_rows: list[list[str]] = []
            for srv in report.server_benchmarks:
                srv_rows.append(
                    [
                        srv.server,
                        str(srv.models_evaluated_count),
                        f"{srv.avg_latency_p50_ms:.1f}ms",
                        f"{srv.avg_throughput_items_per_sec:.1f} items/s",
                        srv.fastest_model,
                        srv.top_score_model,
                    ]
                )
            write_stdout("\n")
            print_table(
                title="🖥️ Backend Server Hardware & Concurrency Performance",
                columns=srv_cols,
                rows=srv_rows,
            )

        # 4. Actionable Recommendations Panel
        if report.recommendations:
            rec_text = "\n".join(f"• {rec}" for rec in report.recommendations)
            write_stdout("\n")
            print_panel(rec_text, title="💡 Architectural Insights & Recommendations")

        print_info(
            f"\n[dim]Report persisted to .data/benchmarks/{report.session_id}/"
            "embedding_report.json[/dim]",
            prefix=False,
        )

    def generate_markdown(self, report: EmbeddingBenchmarkReport) -> str:
        """Generate comprehensive GitHub-flavored markdown report."""
        lines = [
            f"# Embedding Model Benchmark Report ({report.session_id})",
            "",
            "## 🏆 Leaderboard Summary",
            "",
            (
                "| Rank | Model | Server | Dimension | Recall@1 | Recall@3 | "
                "MRR | NDCG@5 | Margin | Latency p50 | Throughput | Overall Score |"
            ),
            (
                "| :--- | :--- | :--- | :--- | :--- | :--- | "
                ":--- | :--- | :--- | :--- | :--- | :--- |"
            ),
        ]
        for rank, res in enumerate(report.models, 1):
            if rank == 1:
                badge = "🥇"
            elif rank == 2:
                badge = "🥈"
            elif rank == 3:
                badge = "🥉"
            else:
                badge = f"#{rank}"
            lines.append(
                f"| {badge} | `{res.model}` | `{res.server}` | {res.dimension} | "
                f"{res.recall_at_1:.1f}% | {res.recall_at_3:.1f}% | {res.mrr:.3f} | "
                f"{res.ndcg_at_5:.3f} | {res.mean_cosine_margin:+.3f} | "
                f"{res.latency_ms_p50:.1f}ms | {res.throughput_items_per_sec:.1f}/s | "
                f"**{res.overall_score:.1f}%** |"
            )

        if len(report.server_benchmarks) > 1:
            lines.extend(
                [
                    "",
                    "## 🖥️ Server Hardware Comparison",
                    "",
                    "| Server | Models Evaluated | Avg Latency (p50) | "
                    "Avg Throughput | Fastest Model | Top Model |",
                    "| :--- | :--- | :--- | :--- | :--- | :--- |",
                ]
            )
            for srv in report.server_benchmarks:
                lines.append(
                    f"| `{srv.server}` | {srv.models_evaluated_count} | "
                    f"{srv.avg_latency_p50_ms:.1f}ms | "
                    f"{srv.avg_throughput_items_per_sec:.1f}/s | "
                    f"`{srv.fastest_model}` | `{srv.top_score_model}` |"
                )

        if report.recommendations:
            lines.extend(
                [
                    "",
                    "## 💡 Key Recommendations",
                    "",
                ]
            )
            for rec in report.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)
