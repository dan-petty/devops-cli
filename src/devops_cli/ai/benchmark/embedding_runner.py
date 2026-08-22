"""Benchmarking engine for evaluating vector embedding models and retrieval quality."""

from __future__ import annotations

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.ai.benchmark.embedding_tasks import (
    EmbeddingEvalPair,
    get_embedding_eval_dataset,
)
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.constants import CONST_DATA_DIR
from devops_cli.config.settings import AIConfig, Settings, get_ai_api_key, load_settings
from devops_cli.models.benchmark import (
    EmbeddingBenchmarkReport,
    EmbeddingBenchmarkResult,
)

logger = logging.getLogger(__name__)
console = Console()


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


class EmbeddingBenchmarkRunner:
    """Orchestrates embedding model latency, throughput, and retrieval benchmarks."""

    def __init__(
        self,
        models: list[str],
        settings: Settings | None = None,
        provider: str | None = None,
        is_dry_run: bool | None = None,
        concurrency: int = 4,
        servers: list[str] | None = None,
    ) -> None:
        self.models = models or ["nomic-embed-text:latest"]
        self.settings = settings or load_settings()
        self.provider = provider or self.settings.ai.provider
        self.session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._is_dry_run_override = is_dry_run
        self.servers = servers or self.settings.ai.ollama_urls or ["http://localhost:11434"]
        self.concurrency = max(1, concurrency)
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
            m_idx = self.models.index(model_name) if model_name in self.models else 0
            endpoint = self.servers[m_idx % len(self.servers)]

        ai_kwargs: dict[str, Any] = {
            "provider": self.provider,
            "rag": {"embedding_model": clean_model},
        }

        if endpoint:
            clean_endpoint = validate_url(endpoint, "benchmark server", allow_private=True)
            ai_kwargs["ollama_urls"] = [clean_endpoint]
            ai_kwargs["api_base_url"] = clean_endpoint

        cfg = AIConfig(**ai_kwargs)
        api_key = get_ai_api_key(self.settings)
        return EmbeddingsEngine(cfg, api_key=api_key)

    def evaluate_model(
        self,
        model_name: str,
        pairs: list[EmbeddingEvalPair],
        corpus: list[str],
    ) -> EmbeddingBenchmarkResult:
        """Execute full benchmark evaluation for a single embedding model."""
        clean_model = model_name.split("@")[0]
        if "@" in model_name:
            server_str = model_name.split("@")[1]
        else:
            server_str = self.servers[0] if self.servers else "default"

        with self._print_lock:
            rprint(
                f"[bold cyan]⏳ Benchmarking embedding model:[/bold cyan] "
                f"{clean_model} [dim]({server_str})[/dim]..."
            )

        if self.is_dry_run_active:
            dim = 768
            return EmbeddingBenchmarkResult(
                model=clean_model,
                server=server_str,
                dimension=dim,
                recall_at_1=100.0,
                recall_at_3=100.0,
                mrr=1.0,
                mean_cosine_margin=0.45,
                latency_ms_p50=12.5,
                latency_ms_p95=18.2,
                throughput_items_per_sec=85.0,
                throughput_chars_per_sec=18500.0,
                overall_score=95.0,
                is_normalized=True,
                category_accuracies={
                    "security": 100.0,
                    "kubernetes": 100.0,
                    "architecture": 100.0,
                    "ci_cd": 100.0,
                    "infrastructure": 100.0,
                },
            )

        engine = self._engine_for_model(model_name)

        # 1. Measure single-query latencies
        query_latencies: list[float] = []
        for pair in pairs[:5]:
            t0 = time.perf_counter()
            try:
                engine.embed_texts([pair.query])
                dur_ms = (time.perf_counter() - t0) * 1000.0
                query_latencies.append(dur_ms)
            except Exception as exc:
                logger.warning("Query embedding failed for %s: %s", clean_model, exc)

        query_latencies.sort()
        p50_lat = query_latencies[len(query_latencies) // 2] if query_latencies else 0.0
        p95_lat = query_latencies[int(len(query_latencies) * 0.95)] if query_latencies else 0.0

        # 2. Measure batch throughput across complete corpus
        total_chars = sum(len(doc) for doc in corpus)
        t_batch_start = time.perf_counter()
        try:
            corpus_vectors = engine.embed_texts(corpus)
            batch_dur = max(time.perf_counter() - t_batch_start, 0.001)
            items_per_sec = len(corpus) / batch_dur
            chars_per_sec = total_chars / batch_dur
        except Exception as exc:
            logger.error("Corpus batch embedding failed for %s: %s", clean_model, exc)
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
            query_vectors = engine.embed_texts(query_texts)
        except Exception as exc:
            logger.error("Query embeddings failed for %s: %s", clean_model, exc)
            query_vectors = []

        # 5. Compute semantic retrieval metrics (Recall@1, Recall@3, MRR, Margin)
        top1_hits = 0
        top3_hits = 0
        reciprocal_ranks: list[float] = []
        margins: list[float] = []
        category_hits: dict[str, list[int]] = {}

        has_all_queries = query_vectors and len(query_vectors) == len(pairs)
        has_all_corpus = corpus_vectors and len(corpus_vectors) == len(corpus)

        if has_all_queries and has_all_corpus:
            for idx, (pair, q_vec) in enumerate(zip(pairs, query_vectors, strict=False)):
                cat = pair.category
                category_hits.setdefault(cat, [])

                scored_passages: list[tuple[int, float]] = []
                for c_idx, c_vec in enumerate(corpus_vectors):
                    sim = cosine_similarity(q_vec, c_vec)
                    scored_passages.append((c_idx, sim))

                scored_passages.sort(key=lambda x: x[1], reverse=True)
                ranked_indices = [idx_and_sim[0] for idx_and_sim in scored_passages]
                target_idx = idx

                if target_idx in ranked_indices:
                    rank = ranked_indices.index(target_idx) + 1
                else:
                    rank = len(corpus)

                rr = 1.0 / rank
                reciprocal_ranks.append(rr)

                target_sim = next((sim for c_i, sim in scored_passages if c_i == target_idx), 0.0)
                best_other_sim = next(
                    (sim for c_i, sim in scored_passages if c_i != target_idx), 0.0
                )
                margins.append(target_sim - best_other_sim)

                if rank == 1:
                    top1_hits += 1
                    category_hits[cat].append(1)
                else:
                    category_hits[cat].append(0)

                if rank <= 3:
                    top3_hits += 1

        total_pairs = max(len(pairs), 1)
        recall_1 = (top1_hits / total_pairs) * 100.0
        recall_3 = (top3_hits / total_pairs) * 100.0
        mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
        mean_margin = (sum(margins) / len(margins)) if margins else 0.0

        cat_accs = {
            cat: (sum(hits) / len(hits) * 100.0) if hits else 0.0
            for cat, hits in category_hits.items()
        }

        # Quality: 60% (Recall@1 + MRR + margin), Performance: 30%, Vector: 10%
        quality_score = (
            (recall_1 * 0.4) + (mrr * 100.0 * 0.4) + (max(0.0, mean_margin * 100.0) * 0.2)
        )
        perf_score = min(100.0, (items_per_sec / 50.0) * 50.0 + max(0.0, (100.0 - p50_lat / 10.0)))
        health_score = 100.0 if (dimension > 0 and is_normalized) else 50.0
        overall = (quality_score * 0.6) + (perf_score * 0.3) + (health_score * 0.1)

        with self._print_lock:
            rprint(
                f"  [bold green]✓[/bold green] {clean_model} | dim={dimension} | "
                f"R@1={recall_1:.0f}% | MRR={mrr:.2f} | p50={p50_lat:.1f}ms | "
                f"{items_per_sec:.1f} items/s → [bold]{overall:.1f}%[/bold]"
            )

        return EmbeddingBenchmarkResult(
            model=clean_model,
            server=server_str,
            dimension=dimension,
            recall_at_1=round(recall_1, 2),
            recall_at_3=round(recall_3, 2),
            mrr=round(mrr, 3),
            mean_cosine_margin=round(mean_margin, 3),
            latency_ms_p50=round(p50_lat, 2),
            latency_ms_p95=round(p95_lat, 2),
            throughput_items_per_sec=round(items_per_sec, 2),
            throughput_chars_per_sec=round(chars_per_sec, 2),
            overall_score=round(overall, 2),
            is_normalized=is_normalized,
            category_accuracies=cat_accs,
        )

    def run(self) -> EmbeddingBenchmarkReport:
        """Execute parallel benchmark across all candidate embedding models."""
        pairs, corpus = get_embedding_eval_dataset()

        rprint("\n[bold]⚡ DevOps CLI Embedding Model Benchmark Suite[/bold]")
        rprint(
            f"[dim]Session: {self.session_id} | Models: {len(self.models)} | "
            f"Evaluation Pairs: {len(pairs)} | Corpus: {len(corpus)} passages[/dim]\n"
        )

        results: list[EmbeddingBenchmarkResult] = []
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(self.models))) as executor:
            future_to_model = {
                executor.submit(self.evaluate_model, m, pairs, corpus): m for m in self.models
            }
            for future in as_completed(future_to_model):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    m_name = future_to_model[future]
                    logger.error("Evaluation error for model %s: %s", m_name, exc)

        results.sort(key=lambda r: r.overall_score, reverse=True)

        report = EmbeddingBenchmarkReport(
            session_id=self.session_id,
            models=results,
            is_dry_run=self.is_dry_run_active,
        )

        self._save_report(report)
        return report

    def _save_report(self, report: EmbeddingBenchmarkReport) -> None:
        """Save benchmark report to disk under .data/benchmarks/<session_id>/."""
        bench_dir = CONST_DATA_DIR / "benchmarks" / self.session_id
        bench_dir.mkdir(parents=True, exist_ok=True)
        report_file = bench_dir / "embedding_report.json"
        report_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved embedding benchmark report to %s", report_file)

    def print_report(self, report: EmbeddingBenchmarkReport, format_type: str = "table") -> None:
        """Render the benchmark report in the requested output format."""
        if format_type.lower() == "json":
            console.print(report.model_dump_json(indent=2))
            return

        if format_type.lower() == "markdown":
            md = self.generate_markdown(report)
            console.print(md)
            return

        table = Table(title=f"Embedding Model Leaderboard — {report.session_id}", expand=True)
        table.add_column("Rank", justify="center", style="dim")
        table.add_column("Model", style="bold cyan")
        table.add_column("Server", style="dim")
        table.add_column("Dim", justify="right")
        table.add_column("Recall@1", justify="right", style="green")
        table.add_column("Recall@3", justify="right")
        table.add_column("MRR", justify="right")
        table.add_column("Margin", justify="right")
        table.add_column("p50 (ms)", justify="right")
        table.add_column("Items/s", justify="right", style="yellow")
        table.add_column("Overall Score", justify="right", style="bold magenta")

        for rank, res in enumerate(report.models, 1):
            if rank == 1:
                badge = "🥇"
            elif rank == 2:
                badge = "🥈"
            elif rank == 3:
                badge = "🥉"
            else:
                badge = f"#{rank}"
            table.add_row(
                badge,
                res.model,
                res.server,
                str(res.dimension),
                f"{res.recall_at_1:.1f}%",
                f"{res.recall_at_3:.1f}%",
                f"{res.mrr:.3f}",
                f"{res.mean_cosine_margin:+.3f}",
                f"{res.latency_ms_p50:.1f}",
                f"{res.throughput_items_per_sec:.1f}",
                f"{res.overall_score:.1f}%",
            )

        console.print(table)
        rprint(
            f"\n[dim]Report written to .data/benchmarks/{report.session_id}/"
            "embedding_report.json[/dim]"
        )

    def generate_markdown(self, report: EmbeddingBenchmarkReport) -> str:
        """Generate GitHub-flavored markdown report table."""
        lines = [
            f"# Embedding Model Benchmark Leaderboard ({report.session_id})",
            "",
            (
                "| Rank | Model | Server | Dimension | Recall@1 | Recall@3 | "
                "MRR | Cosine Margin | Latency p50 | Throughput | Overall Score |"
            ),
            ("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"),
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
                f"{res.mean_cosine_margin:+.3f} | {res.latency_ms_p50:.1f}ms | "
                f"{res.throughput_items_per_sec:.1f}/s | **{res.overall_score:.1f}%** |"
            )
        return "\n".join(lines)
