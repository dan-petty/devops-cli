"""Multi-model benchmark runner, peer-grading evaluation engine, and reporting."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.client import LLMClient
from devops_cli.ai.review_schema import extract_json_block
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.settings import Settings, get_ai_api_key, load_settings
from devops_cli.dry_run.state import is_dry_run
from devops_cli.models.benchmark import (
    BenchmarkReport,
    BenchmarkTask,
    ModelBenchmarkSummary,
    PeerGrade,
    ServerBenchmarkSummary,
    TaskResponse,
)
from devops_cli.output import (
    TablePayload,
    print,
    print_info,
    write_stdout,
)

logger = logging.getLogger(__name__)

_GRADER_PROMPT_TEMPLATE = load_task_prompt("benchmark_peer_grader.md")
_BENCHMARK_TASK_SYSTEM_PROMPT = load_task_prompt("benchmark_system.md").strip()
_BENCHMARK_PEER_GRADER_SYSTEM_PROMPT = load_task_prompt("benchmark_peer_grader_system.md").strip()


def _get_benchmarks_base_dir() -> Path:
    """Resolve benchmarks base directory dynamically from settings."""
    from devops_cli.core.repo import find_top_level_repo_root

    settings = load_settings()
    d = settings.data.benchmarks_dir
    if not d.is_absolute():
        d = (find_top_level_repo_root() / d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _format_model_peer_feedback(m: Any, peer_grades: list[Any]) -> list[str]:
    """Format peer review strengths and improvement areas for a candidate model."""
    score_info = f"{m.overall_percentage:.1f}% Score | {m.average_duration_seconds:.1f}s Latency"
    lines: list[str] = [f"### `{m.model}` ({score_info})\n"]
    m_grades = [
        g for g in peer_grades if g.candidate_model == m.model and g.evaluator_model != m.model
    ]
    if not m_grades:
        m_grades = [g for g in peer_grades if g.candidate_model == m.model]

    all_s: list[str] = []
    all_w: list[str] = []
    for g in m_grades:
        all_s.extend(g.strengths)
        all_w.extend(g.weaknesses)

    top_s = list(dict.fromkeys(s for s in all_s if s))[:3]
    top_w = list(dict.fromkeys(w for w in all_w if w))[:3]

    lines.append("**Key Strengths:**")
    if top_s:
        lines.extend(f"- {str_item}" for str_item in top_s)
    else:
        lines.append("- Baseline responses provided.")

    lines.append("\n**Key Improvement Areas:**")
    if top_w:
        lines.extend(f"- {w_item}" for w_item in top_w)
    else:
        lines.append("- No major deficiencies noted.")
    lines.append("")
    return lines


def _parse_score_value(val: object, default: float = 0.0) -> float:
    """Safely extract float score from int, float, or string."""
    try:
        if isinstance(val, int | float):
            return float(val)
        if isinstance(val, str):
            m = re.search(r"[-+]?\d*\.?\d+", val)
            if m:
                return float(m.group())
    except Exception:
        pass
    return default


def _extract_peer_grade_scores(data: dict[str, Any]) -> tuple[float, float, float, float]:
    """Extract and normalize accuracy, security, completeness, and clarity scores."""
    raw_acc = _parse_score_value(data.get("accuracy_score"), 0.0)
    raw_sec = _parse_score_value(data.get("security_score"), 0.0)
    raw_comp = _parse_score_value(data.get("completeness_score"), 0.0)
    raw_clar = _parse_score_value(data.get("clarity_score"), 0.0)

    # Auto-detect if model scored on a 0.0 to 1.0 probability/ratio scale
    if (
        0.0 < raw_acc <= 1.0
        and 0.0 < raw_sec <= 1.0
        and 0.0 < raw_comp <= 1.0
        and 0.0 < raw_clar <= 1.0
    ):
        raw_acc *= 10.0
        raw_sec *= 10.0
        raw_comp *= 10.0
        raw_clar *= 10.0

    acc = round(min(10.0, max(0.0, raw_acc)), 1)
    sec = round(min(10.0, max(0.0, raw_sec)), 1)
    comp = round(min(10.0, max(0.0, raw_comp)), 1)
    clar = round(min(10.0, max(0.0, raw_clar)), 1)
    return acc, sec, comp, clar


def _format_server_hardware_row(
    s: Any,
    fastest_latency: float,
    multi_server: bool,
) -> list[str]:
    """Format single server hardware performance row."""
    bias_str = (
        f"+{s.server_score_bias:.1f}%" if s.server_score_bias > 0 else f"{s.server_score_bias:.1f}%"
    )
    lat_breakdown = ", ".join(f"{m.split(':')[0]}: {dur}s" for m, dur in s.model_latencies.items())
    is_fastest = (
        multi_server and fastest_latency > 0 and s.generation_duration_avg == fastest_latency
    )
    if is_fastest:
        speed_str = "[bold green]1.00x (fastest)[/bold green]"
    elif multi_server and fastest_latency > 0:
        speed_str = f"{s.generation_duration_avg / fastest_latency:.2f}x slower"
    else:
        speed_str = "1.00x"

    return [
        s.server,
        f"{s.generation_duration_avg:.1f}s",
        speed_str,
        f"{s.total_duration_seconds:.1f}s",
        str(s.tasks_generated_count),
        f"{s.avg_score_awarded:.1f}%",
        bias_str,
        lat_breakdown or "-",
    ]


class BenchmarkRunner:
    """Orchestrates benchmark task execution, response collection, peer-grading, and scoring."""

    def __init__(
        self,
        models: list[str],
        tasks: list[BenchmarkTask],
        settings: Settings | None = None,
        provider: str | None = None,
        is_dry_run: bool | None = None,
        concurrency: int = 4,
        servers: list[str] | None = None,
    ) -> None:
        """Initialize the AI benchmark runner.

        Args:
            models: List of candidate model identifier strings to evaluate.
            tasks: Benchmark evaluation tasks to execute across candidate models.
            settings: Runtime CLI configuration settings.
            provider: LLM provider name (e.g. 'ollama', 'openai', 'claude').
            is_dry_run: Override for dry-run simulation mode.
            concurrency: Number of parallel server workers to run simultaneously.
            servers: List of Ollama backend server endpoints for distributed worker execution.
        """
        self.models = models or ["qwen2.5-coder:7b"]
        self.tasks = tasks
        self.settings = settings or load_settings()
        self.provider = provider or self.settings.ai.provider
        self.session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._is_dry_run_override = is_dry_run
        self.servers = servers or self.settings.ai.ollama_urls or ["http://localhost:11434"]
        self.concurrency = max(1, concurrency)
        self._print_lock = threading.Lock()

    def _client_for_model(
        self,
        model_name: str,
        server_url: str | None = None,
    ) -> LLMClient:
        """Instantiate an LLMClient for a given model override and server endpoint."""
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

        updates: dict[str, Any] = {"model": clean_model}
        if endpoint:
            clean_endpoint = validate_url(
                endpoint,
                "benchmark server",
                allow_private=self.settings.ai.allow_private_network or False,
            )
            updates["ollama_urls"] = [clean_endpoint]
            updates["api_base_url"] = clean_endpoint

        cfg = self.settings.ai.model_copy(update=updates)
        api_key = get_ai_api_key(self.settings)
        return LLMClient(cfg, api_key=api_key)

    def _simulate_response(
        self,
        task: BenchmarkTask,
        model: str,
        server_url: str | None = None,
    ) -> TaskResponse:
        """Simulate realistic model response in dry-run mode."""
        return TaskResponse(
            task_id=task.id,
            model=model,
            provider=self.provider,
            server=server_url or "",
            response=(
                f"[Simulated Response from {model} for {task.id}]\n\n"
                f"Reference Solution Summary:\n{task.expected_solution}"
            ),
            duration_seconds=0.85,
        )

    def _simulate_peer_grade(
        self,
        task: BenchmarkTask,
        candidate_model: str,
        evaluator_model: str,
        server_url: str | None = None,
    ) -> PeerGrade:
        """Simulate realistic peer grading in dry-run mode."""
        # Add slight variation per model for deterministic yet differentiated mock results
        offset = (hash(candidate_model + task.id) % 15) / 10.0
        acc = round(min(10.0, 8.5 + offset * 0.1), 1)
        sec = round(min(10.0, 8.8 + offset * 0.1), 1)
        comp = round(min(10.0, 8.2 + offset * 0.1), 1)
        clar = round(min(10.0, 9.0 + offset * 0.05), 1)
        total = round(acc + sec + comp + clar, 1)
        pct = round((total / 40.0) * 100.0, 1)

        return PeerGrade(
            task_id=task.id,
            candidate_model=candidate_model,
            evaluator_model=evaluator_model,
            server=server_url or "",
            accuracy_score=acc,
            security_score=sec,
            completeness_score=comp,
            clarity_score=clar,
            total_score=total,
            percentage=pct,
            strengths=["Technically accurate", "Follows security best practices"],
            weaknesses=["Could include more edge-case tests"],
            feedback=f"Candidate submission evaluated by {evaluator_model}.",
        )

    def _generate_single_task_response(
        self,
        task: BenchmarkTask,
        client: Any,
        model_name: str,
        server_url: str | None,
        backend: str,
    ) -> TaskResponse:
        """Generate response for a single task and return TaskResponse."""
        with self._print_lock:
            print_info(
                f"  ⏳ task=[cyan]{task.id}[/cyan] | "
                f"model=[bold]{model_name}[/bold] | "
                f"backend=[dim]{backend}[/dim] [dim](generating...)[/dim]",
                prefix=False,
            )
        t0 = time.monotonic()
        try:
            rag_block = ""
            try:
                from devops_cli.ai.rag.investigator import (
                    format_rag_investigation_for_prompt,
                    investigate_rag_context,
                )

                rag_ctx = investigate_rag_context(f"{task.id} {task.prompt[:150]}", top_k=2)
                rag_block = format_rag_investigation_for_prompt(
                    rag_ctx, "Architectural Grounding Context"
                )
            except Exception:
                pass

            user_prompt = f"{task.prompt}{rag_block}"
            res_text = client.chat(
                system=_BENCHMARK_TASK_SYSTEM_PROMPT,
                user=user_prompt,
            )
            duration = time.monotonic() - t0
            with self._print_lock:
                print_info(
                    f"  ✓ task=[cyan]{task.id}[/cyan] | "
                    f"model=[bold]{model_name}[/bold] | "
                    f"backend=[dim]{backend}[/dim] | "
                    f"[yellow]{duration:.1f}s[/yellow]",
                    prefix=False,
                )
            return TaskResponse(
                task_id=task.id,
                model=model_name,
                provider=self.provider,
                server=server_url or "",
                response=res_text,
                duration_seconds=round(duration, 2),
            )
        except Exception as exc:
            duration = time.monotonic() - t0
            logger.warning("Model %s failed on task %s: %s", model_name, task.id, exc)
            with self._print_lock:
                print_info(
                    f"  ✗ task=[cyan]{task.id}[/cyan] | "
                    f"model=[bold]{model_name}[/bold] | "
                    f"backend=[dim]{backend}[/dim] | "
                    f"[yellow]{duration:.1f}s[/yellow] (failed)",
                    prefix=False,
                )
            return TaskResponse(
                task_id=task.id,
                model=model_name,
                provider=self.provider,
                server=server_url or "",
                response=f"Error generating response: {exc}",
                duration_seconds=round(duration, 2),
            )

    def _run_model_generation(
        self,
        model_name: str,
        dry_run: bool,
        server_url: str | None = None,
    ) -> list[TaskResponse]:
        """Execute benchmark tasks on a candidate model sequentially on its assigned server."""
        results: list[TaskResponse] = []
        client = self._client_for_model(model_name, server_url=server_url) if not dry_run else None
        backend = client.backend_info if client else (server_url or self.provider)

        with self._print_lock:
            print_info(
                f"[bold]Evaluating model:[/bold] [cyan]{model_name}[/cyan] [dim]({backend})[/dim]",
                prefix=False,
            )

        for task in self.tasks:
            if dry_run:
                resp = self._simulate_response(task, model_name, server_url=server_url)
                results.append(resp)
                msg = (
                    f"  ✓ task=[cyan]{task.id}[/cyan] | "
                    f"model=[bold]{model_name}[/bold] | "
                    f"backend=[dim]{backend}[/dim] | [yellow]0.8s[/yellow]"
                )
                with self._print_lock:
                    print_info(msg, prefix=False)
                continue

            assert client is not None
            resp = self._generate_single_task_response(
                task=task,
                client=client,
                model_name=model_name,
                server_url=server_url,
                backend=backend,
            )
            results.append(resp)
        return results

    def _run_server_generation(
        self,
        server_url: str | None,
        dry_run: bool,
    ) -> list[TaskResponse]:
        """Execute all benchmark models and tasks sequentially on a dedicated worker server."""
        server_resps: list[TaskResponse] = []
        for model_name in self.models:
            resps = self._run_model_generation(
                model_name=model_name,
                dry_run=dry_run,
                server_url=server_url,
            )
            server_resps.extend(resps)
        return server_resps

    def _grade_single_candidate(
        self,
        task: BenchmarkTask,
        candidate_model: str,
        evaluator_model: str,
        c_resp: TaskResponse,
        client: Any,
        backend: str,
        server_url: str | None,
        dry_run: bool,
    ) -> PeerGrade:
        """Evaluate a single candidate task response with the evaluator model."""
        if dry_run:
            grade = self._simulate_peer_grade(
                task, candidate_model, evaluator_model, server_url=server_url
            )
            with self._print_lock:
                print_info(
                    f"  ✓ task=[cyan]{task.id}[/cyan] | "
                    f"judge=[bold]{evaluator_model}[/bold] | "
                    f"candidate=[dim]{candidate_model}[/dim] | "
                    f"backend=[dim]{backend}[/dim] | "
                    f"[yellow]0.4s[/yellow] → [bold]{grade.percentage:.1f}%[/bold]",
                    prefix=False,
                )
            return grade

        with self._print_lock:
            print_info(
                f"  ⏳ task=[cyan]{task.id}[/cyan] | "
                f"judge=[bold]{evaluator_model}[/bold] | "
                f"candidate=[dim]{candidate_model}[/dim] | "
                f"backend=[dim]{backend}[/dim] [dim](grading...)[/dim]",
                prefix=False,
            )
        t0 = time.monotonic()
        grade = self._evaluate_response(task, c_resp, evaluator_model, client=client)
        grade.server = server_url or ""
        grade_dur = time.monotonic() - t0
        with self._print_lock:
            print_info(
                f"  ✓ task=[cyan]{task.id}[/cyan] | "
                f"judge=[bold]{evaluator_model}[/bold] | "
                f"candidate=[dim]{candidate_model}[/dim] | "
                f"backend=[dim]{backend}[/dim] | "
                f"[yellow]{grade_dur:.1f}s[/yellow] → [bold]{grade.percentage:.1f}%[/bold]",
                prefix=False,
            )
        return grade

    def _run_evaluator_grading(
        self,
        evaluator_model: str,
        resp_map: dict[tuple[str, str], TaskResponse],
        dry_run: bool,
        server_url: str | None = None,
    ) -> list[PeerGrade]:
        """Execute blind peer evaluations with an evaluator model on its assigned server."""
        grades: list[PeerGrade] = []
        client = (
            self._client_for_model(evaluator_model, server_url=server_url) if not dry_run else None
        )
        backend = client.backend_info if client else (server_url or self.provider)

        with self._print_lock:
            print_info(
                f"[bold]Evaluator judge:[/bold] [cyan]{evaluator_model}[/cyan] "
                f"[dim]({backend})[/dim]",
                prefix=False,
            )

        for task in self.tasks:
            for candidate_model in self.models:
                c_resp = resp_map.get((task.id, candidate_model))
                if not c_resp:
                    continue
                grade = self._grade_single_candidate(
                    task=task,
                    candidate_model=candidate_model,
                    evaluator_model=evaluator_model,
                    c_resp=c_resp,
                    client=client,
                    backend=backend,
                    server_url=server_url,
                    dry_run=dry_run,
                )
                grades.append(grade)
        return grades

    def _run_server_grading(
        self,
        server_url: str | None,
        resp_map: dict[tuple[str, str], TaskResponse],
        dry_run: bool,
    ) -> list[PeerGrade]:
        """Execute peer grading across all judges sequentially on a dedicated worker server."""
        server_grades: list[PeerGrade] = []
        for evaluator_model in self.models:
            grades = self._run_evaluator_grading(
                evaluator_model=evaluator_model,
                resp_map=resp_map,
                dry_run=dry_run,
                server_url=server_url,
            )
            server_grades.extend(grades)
        return server_grades

    def execute(self) -> BenchmarkReport:
        """Run complete benchmark workflow across all tasks and candidate models."""
        dry_run = (
            self._is_dry_run_override if self._is_dry_run_override is not None else is_dry_run()
        )
        responses: list[TaskResponse] = []
        peer_grades: list[PeerGrade] = []

        grades: list[PeerGrade] = []

        num_workers = max(1, len(self.servers))
        print_info(
            f"\n[bold blue]=== Starting AI Model Benchmark "
            f"(Session {self.session_id}) ===[/bold blue]",
            prefix=False,
        )
        server_labels = ", ".join(self.servers) if self.servers else "default"
        print_info(
            f"[dim]Models: {len(self.models)} | Tasks: {len(self.tasks)} | "
            f"Workers: {num_workers} ({server_labels})[/dim]\n",
            prefix=False,
        )

        # ── Step 1: Generate Model Responses across all workers ───────────────
        print_info(
            f"[dim]Step 1/2: Generating candidate responses on all workers "
            f"(simultaneous across {num_workers} servers)...[/dim]",
            prefix=False,
        )
        if num_workers > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as pool:
                gen_futures = [
                    pool.submit(self._run_server_generation, s, dry_run) for s in self.servers
                ]
                for f in as_completed(gen_futures):
                    responses.extend(f.result())
        else:
            resps = self._run_server_generation(self.servers[0] if self.servers else None, dry_run)
            responses.extend(resps)

        # ── Step 2: Peer Grading Matrix across all workers ────────────────────
        print_info(
            f"\n[dim]Step 2/2: Cross-model blind peer grading on all workers "
            f"(simultaneous across {num_workers} servers)...[/dim]",
            prefix=False,
        )
        resp_map = {(r.task_id, r.model): r for r in responses}
        if num_workers > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as pool:
                grade_futures = [
                    pool.submit(self._run_server_grading, s, resp_map, dry_run)
                    for s in self.servers
                ]
                for gf in as_completed(grade_futures):
                    grades.extend(gf.result())
        else:
            grades = self._run_server_grading(
                self.servers[0] if self.servers else None,
                resp_map,
                dry_run,
            )

        peer_grades = grades

        # ── Step 3: Compute Leaderboard Aggregates ────────────────────────────
        leaderboard = self._compute_leaderboard(responses, peer_grades)
        server_benchmarks = self._compute_server_summaries(responses, peer_grades)

        report = BenchmarkReport(
            session_id=self.session_id,
            models_evaluated=self.models,
            tasks_run=self.tasks,
            responses=responses,
            peer_grades=peer_grades,
            leaderboard=leaderboard,
            server_benchmarks=server_benchmarks,
            is_dry_run=dry_run,
        )

        self._save_report(report)
        return report

    def _evaluate_response(
        self,
        task: BenchmarkTask,
        response: TaskResponse,
        evaluator_model: str,
        client: LLMClient | None = None,
    ) -> PeerGrade:
        """Call evaluator model with grading prompt and parse structured score."""
        eval_client = client or self._client_for_model(evaluator_model)
        prompt_text = (
            _GRADER_PROMPT_TEMPLATE.replace("{task_title}", task.title)
            .replace("{task_category}", task.category)
            .replace("{task_prompt}", task.prompt)
            .replace("{expected_solution}", task.expected_solution)
            .replace("{evaluation_rubric}", task.evaluation_rubric)
            .replace("{candidate_response}", response.response)
        )

        err_msg = ""
        try:
            res = eval_client.chat(
                system=_BENCHMARK_PEER_GRADER_SYSTEM_PROMPT,
                user=prompt_text,
            )
            data = extract_json_block(res)
            if isinstance(data, dict):
                acc, sec, comp, clar = _extract_peer_grade_scores(data)
                total = round(acc + sec + comp + clar, 1)
                pct = round((total / 40.0) * 100.0, 1)

                return PeerGrade(
                    task_id=task.id,
                    candidate_model=response.model,
                    evaluator_model=evaluator_model,
                    accuracy_score=acc,
                    security_score=sec,
                    completeness_score=comp,
                    clarity_score=clar,
                    total_score=total,
                    percentage=pct,
                    strengths=list(data.get("strengths", [])),
                    weaknesses=list(data.get("weaknesses", [])),
                    feedback=str(data.get("feedback", "")),
                )
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("Peer evaluation failed: %s", exc)

        # Fallback default score on parse error (0.0 default; discarded as invalid during scoring)
        return PeerGrade(
            task_id=task.id,
            candidate_model=response.model,
            evaluator_model=evaluator_model,
            accuracy_score=0.0,
            security_score=0.0,
            completeness_score=0.0,
            clarity_score=0.0,
            total_score=0.0,
            percentage=0.0,
            feedback=f"Evaluation default due to parsing error: {err_msg}",
        )

    def _calculate_single_model_summary(
        self,
        model: str,
        valid_grades: list[PeerGrade],
        responses: list[TaskResponse],
        judge_weights: dict[str, float],
        judge_offsets: dict[str, float],
        task_cat_map: Mapping[str, str],
        task_weight_map: dict[str, float],
    ) -> ModelBenchmarkSummary:
        """Compute aggregated performance and peer evaluation metrics for a single model."""
        m_valid_grades = [g for g in valid_grades if g.candidate_model == model]
        m_peer_grades = [g for g in m_valid_grades if g.evaluator_model != model]
        evals_to_score = m_valid_grades
        m_resps = [r for r in responses if r.model == model]

        avg_dur = sum(r.duration_seconds for r in m_resps) / len(m_resps) if m_resps else 0.0

        if not evals_to_score:
            return ModelBenchmarkSummary(
                model=model,
                provider=self.provider,
                average_duration_seconds=round(avg_dur, 2),
                judge_weight=judge_weights.get(model, 1.0),
                valid_evaluations_count=0,
            )

        # Weight each evaluation by: Judge_Weight(evaluator) * Task_Weight(task)
        total_eval_weight = sum(
            judge_weights.get(g.evaluator_model, 1.0) * task_weight_map.get(g.task_id, 1.0)
            for g in evals_to_score
        )
        total_judge_weight = sum(judge_weights.get(g.evaluator_model, 1.0) for g in evals_to_score)

        if total_eval_weight > 0:
            calibrated_sum = sum(
                max(
                    0.0,
                    min(100.0, g.percentage - (judge_offsets.get(g.evaluator_model, 0.0) * 0.5)),
                )
                * judge_weights.get(g.evaluator_model, 1.0)
                * task_weight_map.get(g.task_id, 1.0)
                for g in evals_to_score
            )
            weighted_pct = calibrated_sum / total_eval_weight
        else:
            weighted_pct = 0.0

        # Compute pure peer-only percentage (excluding self-assessment)
        if m_peer_grades:
            total_peer_w = sum(
                judge_weights.get(g.evaluator_model, 1.0) * task_weight_map.get(g.task_id, 1.0)
                for g in m_peer_grades
            )
            peer_pct = (
                sum(
                    g.percentage
                    * judge_weights.get(g.evaluator_model, 1.0)
                    * task_weight_map.get(g.task_id, 1.0)
                    for g in m_peer_grades
                )
                / total_peer_w
                if total_peer_w > 0
                else 0.0
            )
        else:
            peer_pct = weighted_pct

        # Compute self-preference bias
        m_self_grades = [g for g in m_valid_grades if g.evaluator_model == model]
        if m_self_grades and m_peer_grades:
            self_avg = sum(g.percentage for g in m_self_grades) / len(m_self_grades)
            peer_avg = sum(g.percentage for g in m_peer_grades) / len(m_peer_grades)
            self_bias = round(self_avg - peer_avg, 1)
        else:
            self_bias = 0.0

        if total_judge_weight > 0:
            acc_avg = (
                sum(
                    g.accuracy_score * judge_weights.get(g.evaluator_model, 1.0)
                    for g in evals_to_score
                )
                / total_judge_weight
            )
            sec_avg = (
                sum(
                    g.security_score * judge_weights.get(g.evaluator_model, 1.0)
                    for g in evals_to_score
                )
                / total_judge_weight
            )
            comp_avg = (
                sum(
                    g.completeness_score * judge_weights.get(g.evaluator_model, 1.0)
                    for g in evals_to_score
                )
                / total_judge_weight
            )
            clar_avg = (
                sum(
                    g.clarity_score * judge_weights.get(g.evaluator_model, 1.0)
                    for g in evals_to_score
                )
                / total_judge_weight
            )
        else:
            acc_avg = sec_avg = comp_avg = clar_avg = 0.0

        # Category scores (weighted by judge weight)
        cat_totals: dict[str, float] = {}
        cat_weights: dict[str, float] = {}
        for g in evals_to_score:
            cat = task_cat_map.get(g.task_id, "general")
            jw = judge_weights.get(g.evaluator_model, 1.0)
            cat_totals[cat] = cat_totals.get(cat, 0.0) + (g.percentage * jw)
            cat_weights[cat] = cat_weights.get(cat, 0.0) + jw

        cat_avg = {
            cat: round(cat_totals[cat] / cat_weights[cat], 1)
            for cat in cat_totals
            if cat_weights[cat] > 0
        }

        # Calculate judge strictness/leniency index vs overall consensus
        m_given = [g for g in valid_grades if g.evaluator_model == model]
        if m_given and valid_grades:
            all_avg = sum(g.percentage for g in valid_grades) / len(valid_grades)
            strictness = round((sum(g.percentage for g in m_given) / len(m_given)) - all_avg, 1)
        else:
            strictness = 0.0

        return ModelBenchmarkSummary(
            model=model,
            provider=self.provider,
            overall_percentage=round(weighted_pct, 1),
            peer_only_percentage=round(peer_pct, 1),
            self_preference_bias=self_bias,
            accuracy_avg=round(acc_avg, 1),
            security_avg=round(sec_avg, 1),
            completeness_avg=round(comp_avg, 1),
            clarity_avg=round(clar_avg, 1),
            category_scores=cat_avg,
            average_duration_seconds=round(avg_dur, 2),
            grading_strictness_index=strictness,
            judge_weight=judge_weights.get(model, 1.0),
            valid_evaluations_count=len(m_valid_grades),
        )

    def _compute_leaderboard(
        self,
        responses: list[TaskResponse],
        grades: list[PeerGrade],
    ) -> list[ModelBenchmarkSummary]:
        """Aggregate peer grades into per-model metrics."""
        task_cat_map = {t.id: t.category for t in self.tasks}
        task_weight_map = {t.id: t.weight for t in self.tasks}

        valid_grades = [
            g
            for g in grades
            if g.total_score > 0.0
            and (
                g.accuracy_score > 0.0
                or g.security_score > 0.0
                or g.completeness_score > 0.0
                or g.clarity_score > 0.0
            )
        ]

        # Phase 1: Compute peer competence baseline to determine judge weights
        raw_competence: dict[str, float] = {}
        for model in self.models:
            m_peer_received = [
                g for g in valid_grades if g.candidate_model == model and g.evaluator_model != model
            ]
            evals = (
                m_peer_received
                if m_peer_received
                else [g for g in valid_grades if g.candidate_model == model]
            )
            if evals:
                total_w = sum(task_weight_map.get(g.task_id, 1.0) for g in evals)
                raw_pct = (
                    sum(g.percentage * task_weight_map.get(g.task_id, 1.0) for g in evals) / total_w
                    if total_w > 0
                    else 0.0
                )
                raw_competence[model] = raw_pct
            else:
                raw_competence[model] = 0.0

        # Judge weights: Top model gets full weight (1.00), worst model gets almost no weight (0.01)
        judge_weights: dict[str, float] = {}
        if len(self.models) > 1 and raw_competence:
            max_comp = max(raw_competence.values())
            min_comp = min(raw_competence.values())
            comp_span = max_comp - min_comp
            for model, comp in raw_competence.items():
                if comp_span > 0.0:
                    rel_score = (comp - min_comp) / comp_span
                    # Quadratic scaling: worst model -> 0.01, top model -> 1.00
                    w = 0.01 + 0.99 * (rel_score**2)
                    judge_weights[model] = round(w, 3)
                else:
                    judge_weights[model] = 1.0
        else:
            for model in self.models:
                judge_weights[model] = 1.0

        # Phase 2: Compute judge strictness/leniency calibration offsets
        judge_offsets: dict[str, float] = {}
        if len(self.models) >= 3 and valid_grades:
            all_eval_avg = sum(g.percentage for g in valid_grades) / len(valid_grades)
            for m in self.models:
                m_given = [g for g in valid_grades if g.evaluator_model == m]
                judge_offsets[m] = (
                    (sum(g.percentage for g in m_given) / len(m_given)) - all_eval_avg
                    if m_given
                    else 0.0
                )
        else:
            for m in self.models:
                judge_offsets[m] = 0.0

        # Phase 3: Compute weighted metrics per model
        summaries = [
            self._calculate_single_model_summary(
                model=model,
                valid_grades=valid_grades,
                responses=responses,
                judge_weights=judge_weights,
                judge_offsets=judge_offsets,
                task_cat_map=task_cat_map,
                task_weight_map=task_weight_map,
            )
            for model in self.models
        ]
        summaries.sort(key=lambda s: s.overall_percentage, reverse=True)
        return summaries

    def _calculate_single_server_summary(
        self,
        s_url: str,
        responses: list[TaskResponse],
        valid_grades: list[PeerGrade],
        global_avg_score: float,
    ) -> ServerBenchmarkSummary:
        """Aggregate per-server execution duration, model latency, and judge scoring bias."""
        s_responses = [
            r for r in responses if (r.server == s_url or (not r.server and s_url == "default"))
        ]
        s_grades = [
            g for g in valid_grades if (g.server == s_url or (not g.server and s_url == "default"))
        ]

        gen_avg = (
            sum(r.duration_seconds for r in s_responses) / len(s_responses) if s_responses else 0.0
        )
        total_dur = sum(r.duration_seconds for r in s_responses)

        m_latencies: dict[str, float] = {}
        for m in self.models:
            m_resps = [r for r in s_responses if r.model == m]
            if m_resps:
                m_latencies[m] = round(sum(r.duration_seconds for r in m_resps) / len(m_resps), 1)

        avg_score = sum(g.percentage for g in s_grades) / len(s_grades) if s_grades else 0.0
        server_bias = (
            round(avg_score - global_avg_score, 2) if (s_grades and global_avg_score > 0) else 0.0
        )

        return ServerBenchmarkSummary(
            server=s_url,
            generation_duration_avg=round(gen_avg, 2),
            total_duration_seconds=round(total_dur, 2),
            tasks_generated_count=len(s_responses),
            evaluations_performed_count=len(s_grades),
            avg_score_awarded=round(avg_score, 1),
            server_score_bias=server_bias,
            model_latencies=m_latencies,
        )

    def _compute_server_summaries(
        self,
        responses: list[TaskResponse],
        peer_grades: list[PeerGrade],
    ) -> list[ServerBenchmarkSummary]:
        """Aggregate per-server execution duration, model latency, and judge scoring bias."""
        server_keys: set[str] = set()
        for r in responses:
            if r.server:
                server_keys.add(r.server)
        for g in peer_grades:
            if g.server:
                server_keys.add(g.server)

        if not server_keys and self.servers:
            server_keys.update(self.servers)
        if not server_keys:
            server_keys.add("default")

        valid_grades = [
            g
            for g in peer_grades
            if g.percentage > 0.0
            or any([g.accuracy_score > 0, g.security_score > 0, g.completeness_score > 0])
        ]
        global_avg_score = (
            sum(g.percentage for g in valid_grades) / len(valid_grades) if valid_grades else 0.0
        )

        summaries = [
            self._calculate_single_server_summary(
                s_url=s_url,
                responses=responses,
                valid_grades=valid_grades,
                global_avg_score=global_avg_score,
            )
            for s_url in sorted(server_keys)
        ]
        summaries.sort(key=lambda s: s.generation_duration_avg)
        return summaries

    def _save_report(self, report: BenchmarkReport) -> Path:
        """Persist structured benchmark report to JSON artifact."""
        out_dir = _get_benchmarks_base_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{report.session_id}-benchmark.json"
        out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved benchmark report to %s", out_path)
        return out_path

    def render_results(self, report: BenchmarkReport) -> None:
        """Print summary tables and leaderboards to console."""
        columns = [
            ("Rank", "bold"),
            ("Model", "cyan"),
            ("Score", "bold green"),
            ("Peer Score", "green"),
            "Accuracy",
            "Security",
            "Complete",
            "Clarity",
            ("Judge Wt", "magenta"),
            ("Latency", "dim"),
            ("Bias (Judge)", "dim"),
            ("Self-Bias", "yellow"),
        ]
        rows: list[list[str]] = []
        for rank_index, model_summary in enumerate(report.leaderboard, start=1):
            rank_badge = (
                "🥇"
                if rank_index == 1
                else ("🥈" if rank_index == 2 else ("🥉" if rank_index == 3 else f"#{rank_index}"))
            )
            bias_str = (
                f"+{model_summary.grading_strictness_index:.1f}%"
                if model_summary.grading_strictness_index > 0
                else f"{model_summary.grading_strictness_index:.1f}%"
            )
            if model_summary.self_preference_bias < -5.0:
                self_bias_str = f"[green]{model_summary.self_preference_bias:.1f}%[/green] (strict)"
            elif model_summary.self_preference_bias > 15.0:
                self_bias_str = f"[red]+{model_summary.self_preference_bias:.1f}%[/red] (inflated)"
            elif model_summary.self_preference_bias > 0:
                self_bias_str = f"+{model_summary.self_preference_bias:.1f}%"
            else:
                self_bias_str = f"{model_summary.self_preference_bias:.1f}%"
            rows.append(
                [
                    rank_badge,
                    model_summary.model,
                    f"{model_summary.overall_percentage:.1f}%",
                    f"{model_summary.peer_only_percentage:.1f}%",
                    f"{model_summary.accuracy_avg * 10.0:.1f}%",
                    f"{model_summary.security_avg * 10.0:.1f}%",
                    f"{model_summary.completeness_avg * 10.0:.1f}%",
                    f"{model_summary.clarity_avg * 10.0:.1f}%",
                    f"{model_summary.judge_weight:.2f}",
                    f"{model_summary.average_duration_seconds:.1f}s",
                    bias_str,
                    self_bias_str,
                ]
            )

        base_bench_dir = _get_benchmarks_base_dir()
        report_path = base_bench_dir / f"{report.session_id}-benchmark.json"
        write_stdout("\n")
        leaderboard_table = TablePayload(
            title=f"AI Benchmark Leaderboard (Session {report.session_id})",
            columns=columns,
            rows=rows,
        )
        print(leaderboard_table)

        if len(report.tasks_run) > 1:
            categories = sorted({task.category for task in report.tasks_run})
            category_columns: list[Any] = [("Model", "cyan")]
            for category in categories:
                category_columns.append(category.capitalize())

            category_rows: list[list[str]] = []
            for model_summary in report.leaderboard:
                row = [model_summary.model]
                for category in categories:
                    score = model_summary.category_scores.get(category, 0.0)
                    row.append(f"{score:.1f}%")
                category_rows.append(row)

            write_stdout("\n")
            category_table = TablePayload(
                title=f"Domain Category Breakdown (Session {report.session_id})",
                columns=category_columns,
                rows=category_rows,
            )
            print(category_table)

        if report.server_benchmarks:
            server_cols: list[Any] = [
                ("Server / Worker Node", "cyan"),
                ("Avg Latency", "bold yellow"),
                ("Speed Factor", "magenta"),
                ("Total Time", "dim"),
                ("Tasks", "dim"),
                ("Avg Score Given", "magenta"),
                "Server Bias",
                ("Per-Model Latency Breakdown", "dim"),
            ]

            fastest_latency = min(
                (
                    server_summary.generation_duration_avg
                    for server_summary in report.server_benchmarks
                    if server_summary.generation_duration_avg > 0
                ),
                default=0.0,
            )

            server_rows: list[list[str]] = []
            multi_server = len(report.server_benchmarks) > 1
            for server_summary in report.server_benchmarks:
                server_rows.append(
                    _format_server_hardware_row(server_summary, fastest_latency, multi_server)
                )

            write_stdout("\n")
            server_table = TablePayload(
                title=f"Ollama Server Hardware & Node Performance (Session {report.session_id})",
                columns=server_cols,
                rows=server_rows,
            )
            print(server_table)

        print(f"Detailed benchmark report saved → [cyan]{report_path}[/cyan]", level="success")

    def to_markdown(self, report: BenchmarkReport) -> str:
        """Generate a clean GitHub-flavored Markdown benchmark report."""
        table_hdr = (
            "| Rank | Model | Score | Peer | Accuracy | Security | "
            "Complete | Clarity | Judge Wt | Latency | Self-Bias |"
        )
        table_sep = (
            "| :---: | :--- | :---: | :---: | :---: | :---: | "
            ":---: | :---: | :---: | :---: | :---: |"
        )

        lines: list[str] = [
            f"# AI Benchmark Report (Session `{report.session_id}`)\n",
            f"- **Timestamp**: `{report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}`",
            f"- **Models**: {', '.join(f'`{m}`' for m in report.models_evaluated)}",
            f"- **Tasks**: {len(report.tasks_run)}",
            f"- **Workers**: {len(self.servers)}\n",
            "## Leaderboard\n",
            table_hdr,
            table_sep,
        ]

        for idx, m in enumerate(report.leaderboard, start=1):
            rank_badge = (
                "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"#{idx}"))
            )
            self_bias_str = (
                f"+{m.self_preference_bias:.1f}%"
                if m.self_preference_bias > 0
                else f"{m.self_preference_bias:.1f}%"
            )
            row = (
                f"| {rank_badge} | `{m.model}` | **{m.overall_percentage:.1f}%** | "
                f"{m.peer_only_percentage:.1f}% | {m.accuracy_avg * 10.0:.1f}% | "
                f"{m.security_avg * 10.0:.1f}% | {m.completeness_avg * 10.0:.1f}% | "
                f"{m.clarity_avg * 10.0:.1f}% | {m.judge_weight:.2f} | "
                f"{m.average_duration_seconds:.1f}s | {self_bias_str} |"
            )
            lines.append(row)

        if len(report.tasks_run) > 1:
            lines.append("\n## Domain Category Breakdown\n")
            categories = sorted({t.category for t in report.tasks_run})
            cat_headers = " | ".join(c.capitalize() for c in categories)
            lines.append(f"| Model | {cat_headers} |")
            lines.append(f"| :--- | {' | '.join(':---:' for _ in categories)} |")

            for m in report.leaderboard:
                cat_vals = " | ".join(f"{m.category_scores.get(c, 0.0):.1f}%" for c in categories)
                lines.append(f"| `{m.model}` | {cat_vals} |")

        if report.server_benchmarks:
            lines.append("\n## Server Performance & Score Bias\n")
            lines.append(
                "| Server / Worker | Avg Latency | Speed Factor | Total Time | Tasks | "
                "Avg Score Given | Server Bias | Per-Model Latencies |"
            )
            lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
            fastest_lat = min(
                (
                    s.generation_duration_avg
                    for s in report.server_benchmarks
                    if s.generation_duration_avg > 0
                ),
                default=0.0,
            )
            for s in report.server_benchmarks:
                bias_str = (
                    f"+{s.server_score_bias:.1f}%"
                    if s.server_score_bias > 0
                    else f"{s.server_score_bias:.1f}%"
                )
                lat_breakdown = ", ".join(
                    f"{m.split(':')[0]}: {dur}s" for m, dur in s.model_latencies.items()
                )
                is_fastest = (
                    len(report.server_benchmarks) > 1
                    and fastest_lat > 0
                    and s.generation_duration_avg == fastest_lat
                )
                if is_fastest:
                    speed_str = "1.00x (fastest)"
                elif len(report.server_benchmarks) > 1 and fastest_lat > 0:
                    speed_str = f"{s.generation_duration_avg / fastest_lat:.2f}x slower"
                else:
                    speed_str = "1.00x"

                lines.append(
                    f"| `{s.server}` | {s.generation_duration_avg:.1f}s | {speed_str} | "
                    f"{s.total_duration_seconds:.1f}s | {s.tasks_generated_count} | "
                    f"{s.avg_score_awarded:.1f}% | {bias_str} | {lat_breakdown or '-'} |"
                )

        if report.peer_grades:
            lines.append("\n## Model Strengths & Improvement Areas (Peer Feedback)\n")
            for m in report.leaderboard:
                lines.extend(_format_model_peer_feedback(m, report.peer_grades))

        return "\n".join(lines)
