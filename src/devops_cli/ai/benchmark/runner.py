"""Multi-model benchmark runner, peer-grading evaluation engine, and reporting."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.ai.client import LLMClient
from devops_cli.ai.review_schema import extract_json_block
from devops_cli.config.constants import CONST_DATA_DIR
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

logger = logging.getLogger(__name__)
console = Console()

_TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def _load_task_prompt(filename: str) -> str:
    path = _TASKS_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


_GRADER_PROMPT_TEMPLATE = _load_task_prompt("benchmark_peer_grader.md")


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
            updates["ollama_urls"] = [endpoint]
            updates["api_base_url"] = endpoint

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
            rprint(
                f"[bold]Evaluating model:[/bold] [cyan]{model_name}[/cyan] [dim]({backend})[/dim]"
            )

        for task in self.tasks:
            if dry_run:
                resp = self._simulate_response(task, model_name, server_url=server_url)
                results.append(resp)
                with self._print_lock:
                    rprint(
                        f"  ✓ task=[cyan]{task.id}[/cyan] | "
                        f"model=[bold]{model_name}[/bold] | "
                        f"backend=[dim]{backend}[/dim] | "
                        f"[yellow]0.8s[/yellow]"
                    )
                continue

            assert client is not None
            with self._print_lock:
                rprint(
                    f"  ⏳ task=[cyan]{task.id}[/cyan] | "
                    f"model=[bold]{model_name}[/bold] | "
                    f"backend=[dim]{backend}[/dim] [dim](generating...)[/dim]"
                )
            t0 = time.monotonic()
            try:
                res_text = client.chat(
                    system="You are an expert DevOps and DevSecOps staff engineer.",
                    user=task.prompt,
                )
                duration = time.monotonic() - t0
                results.append(
                    TaskResponse(
                        task_id=task.id,
                        model=model_name,
                        provider=self.provider,
                        server=server_url or "",
                        response=res_text,
                        duration_seconds=round(duration, 2),
                    )
                )
                with self._print_lock:
                    rprint(
                        f"  ✓ task=[cyan]{task.id}[/cyan] | "
                        f"model=[bold]{model_name}[/bold] | "
                        f"backend=[dim]{backend}[/dim] | "
                        f"[yellow]{duration:.1f}s[/yellow]"
                    )
            except Exception as exc:
                duration = time.monotonic() - t0
                logger.warning("Model %s failed on task %s: %s", model_name, task.id, exc)
                results.append(
                    TaskResponse(
                        task_id=task.id,
                        model=model_name,
                        provider=self.provider,
                        server=server_url or "",
                        response=f"Error generating response: {exc}",
                        duration_seconds=round(duration, 2),
                    )
                )
                with self._print_lock:
                    rprint(
                        f"  ✗ task=[cyan]{task.id}[/cyan] | "
                        f"model=[bold]{model_name}[/bold] | "
                        f"backend=[dim]{backend}[/dim] | "
                        f"[yellow]{duration:.1f}s[/yellow] (failed)"
                    )
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
            rprint(
                f"[bold]Evaluator judge:[/bold] [cyan]{evaluator_model}[/cyan] "
                f"[dim]({backend})[/dim]"
            )

        for task in self.tasks:
            for candidate_model in self.models:
                c_resp = resp_map.get((task.id, candidate_model))
                if not c_resp:
                    continue

                if dry_run:
                    grade = self._simulate_peer_grade(
                        task, candidate_model, evaluator_model, server_url=server_url
                    )
                    grades.append(grade)
                    with self._print_lock:
                        rprint(
                            f"  ✓ task=[cyan]{task.id}[/cyan] | "
                            f"judge=[bold]{evaluator_model}[/bold] | "
                            f"candidate=[dim]{candidate_model}[/dim] | "
                            f"backend=[dim]{backend}[/dim] | "
                            f"[yellow]0.4s[/yellow] → [bold]{grade.percentage:.1f}%[/bold]"
                        )
                    continue

                with self._print_lock:
                    rprint(
                        f"  ⏳ task=[cyan]{task.id}[/cyan] | "
                        f"judge=[bold]{evaluator_model}[/bold] | "
                        f"candidate=[dim]{candidate_model}[/dim] | "
                        f"backend=[dim]{backend}[/dim] [dim](grading...)[/dim]"
                    )
                t0 = time.monotonic()
                grade = self._evaluate_response(task, c_resp, evaluator_model, client=client)
                grade.server = server_url or ""
                grade_dur = time.monotonic() - t0
                grades.append(grade)
                with self._print_lock:
                    rprint(
                        f"  ✓ task=[cyan]{task.id}[/cyan] | "
                        f"judge=[bold]{evaluator_model}[/bold] | "
                        f"candidate=[dim]{candidate_model}[/dim] | "
                        f"backend=[dim]{backend}[/dim] | "
                        f"[yellow]{grade_dur:.1f}s[/yellow] → [bold]{grade.percentage:.1f}%[/bold]"
                    )
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

        num_servers = len(self.servers) if self.servers else 1
        num_workers = min(self.concurrency, num_servers)

        rprint(
            f"[bold cyan]Starting AI Benchmark Suite[/bold cyan] "
            f"([green]{len(self.models)}[/green] models, [green]{len(self.tasks)}[/green] tasks, "
            f"[yellow]{num_workers}[/yellow] concurrent server worker(s))"
        )

        # ── Step 1: Generate Model Responses across all workers ───────────────
        rprint(
            f"[dim]Step 1/2: Generating candidate responses on all workers "
            f"(simultaneous across {num_workers} servers)...[/dim]"
        )
        server_responses: dict[str, list[TaskResponse]] = {}

        if num_workers > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_server = {
                    executor.submit(
                        self._run_server_generation,
                        self.servers[i],
                        dry_run,
                    ): self.servers[i]
                    for i in range(num_workers)
                }
                for f in as_completed(future_to_server):
                    s_url = future_to_server[f]
                    resps = f.result()
                    server_responses[s_url] = resps
                    responses.extend(resps)
        else:
            s_url = self.servers[0] if self.servers else "default"
            resps = self._run_server_generation(self.servers[0] if self.servers else None, dry_run)
            server_responses[s_url] = resps
            responses.extend(resps)

        # ── Step 2: Peer Grading Matrix across all workers ────────────────────
        rprint(
            f"\n[dim]Step 2/2: Cross-model blind peer grading on all workers "
            f"(simultaneous across {num_workers} servers)...[/dim]"
        )

        if num_workers > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as grade_executor:
                grade_futures = [
                    grade_executor.submit(
                        self._run_server_grading,
                        self.servers[i],
                        {
                            (r.task_id, r.model): r
                            for r in server_responses.get(self.servers[i], responses)
                        },
                        dry_run,
                    )
                    for i in range(num_workers)
                ]
                for gf in as_completed(grade_futures):
                    peer_grades.extend(gf.result())
        else:
            s_url = self.servers[0] if self.servers else "default"
            resp_map = {(r.task_id, r.model): r for r in server_responses.get(s_url, responses)}
            peer_grades.extend(
                self._run_server_grading(
                    self.servers[0] if self.servers else None,
                    resp_map,
                    dry_run,
                )
            )

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
                system=(
                    "You are an expert AI peer evaluation judge reviewing an anonymous "
                    "candidate response against reference criteria. Return valid JSON only."
                ),
                user=prompt_text,
            )
            data = extract_json_block(res)
            if isinstance(data, dict):
                import re

                def _parse_score(val: object, default: float = 0.0) -> float:
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

                raw_acc = _parse_score(data.get("accuracy_score"), 0.0)
                raw_sec = _parse_score(data.get("security_score"), 0.0)
                raw_comp = _parse_score(data.get("completeness_score"), 0.0)
                raw_clar = _parse_score(data.get("clarity_score"), 0.0)

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

    def _compute_leaderboard(
        self,
        responses: list[TaskResponse],
        grades: list[PeerGrade],
    ) -> list[ModelBenchmarkSummary]:
        """Aggregate peer grades into per-model metrics.

        Filters out invalid default evaluations and weights judge influence by model competence.
        """
        task_cat_map = {t.id: t.category for t in self.tasks}
        task_weight_map = {t.id: t.weight for t in self.tasks}

        # Discard invalid / default evaluations (where all scores or total_score is 0.0)
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

        # Phase 1: Compute peer competence (excluding self-grading) to determine judge weights
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

        # Judge weights: proportional to model peer competence (scaled to [0.05, 1.0])
        max_comp = max(raw_competence.values()) if raw_competence else 0.0
        judge_weights: dict[str, float] = {}
        for model, comp in raw_competence.items():
            if max_comp > 0:
                judge_weights[model] = round(max(0.05, comp / 100.0), 3)
            else:
                judge_weights[model] = 1.0

        # Phase 2: Compute judge strictness/leniency calibration offsets (active for >= 3 judges)
        judge_offsets: dict[str, float] = {}
        if len(self.models) >= 3 and valid_grades:
            all_eval_avg = sum(g.percentage for g in valid_grades) / len(valid_grades)
            for m in self.models:
                m_given = [g for g in valid_grades if g.evaluator_model == m]
                if m_given:
                    judge_offsets[m] = (
                        sum(g.percentage for g in m_given) / len(m_given)
                    ) - all_eval_avg
                else:
                    judge_offsets[m] = 0.0
        else:
            for m in self.models:
                judge_offsets[m] = 0.0

        # Phase 3: Compute debiased peer-only metrics for each candidate model
        summaries: list[ModelBenchmarkSummary] = []

        for model in self.models:
            m_valid_grades = [g for g in valid_grades if g.candidate_model == model]
            m_peer_grades = [g for g in m_valid_grades if g.evaluator_model != model]
            evals_to_score = m_peer_grades if m_peer_grades else m_valid_grades
            m_resps = [r for r in responses if r.model == model]

            avg_dur = sum(r.duration_seconds for r in m_resps) / len(m_resps) if m_resps else 0.0

            if not evals_to_score:
                summaries.append(
                    ModelBenchmarkSummary(
                        model=model,
                        provider=self.provider,
                        average_duration_seconds=round(avg_dur, 2),
                        judge_weight=judge_weights.get(model, 1.0),
                        valid_evaluations_count=0,
                    )
                )
                continue

            # Weight each evaluation by: Judge_Weight(evaluator) * Task_Weight(task)
            total_eval_weight = sum(
                judge_weights.get(g.evaluator_model, 1.0) * task_weight_map.get(g.task_id, 1.0)
                for g in evals_to_score
            )
            total_judge_weight = sum(
                judge_weights.get(g.evaluator_model, 1.0) for g in evals_to_score
            )

            if total_eval_weight > 0:
                # Calibrate grade against judge leniency offset (damping=0.5)
                weighted_pct = (
                    sum(
                        max(
                            0.0,
                            min(
                                100.0,
                                g.percentage - (judge_offsets.get(g.evaluator_model, 0.0) * 0.5),
                            ),
                        )
                        * judge_weights.get(g.evaluator_model, 1.0)
                        * task_weight_map.get(g.task_id, 1.0)
                        for g in evals_to_score
                    )
                    / total_eval_weight
                )
            else:
                weighted_pct = 0.0

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

            strictness = round(judge_offsets.get(model, 0.0), 2)

            summaries.append(
                ModelBenchmarkSummary(
                    model=model,
                    provider=self.provider,
                    overall_percentage=round(weighted_pct, 1),
                    peer_only_percentage=round(weighted_pct, 1),
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
            )

        summaries.sort(key=lambda s: s.overall_percentage, reverse=True)
        return summaries

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

        summaries: list[ServerBenchmarkSummary] = []

        for s_url in sorted(server_keys):
            s_responses = [
                r for r in responses if (r.server == s_url or (not r.server and s_url == "default"))
            ]
            s_grades = [
                g
                for g in valid_grades
                if (g.server == s_url or (not g.server and s_url == "default"))
            ]

            gen_avg = (
                sum(r.duration_seconds for r in s_responses) / len(s_responses)
                if s_responses
                else 0.0
            )
            total_dur = sum(r.duration_seconds for r in s_responses)

            m_latencies: dict[str, float] = {}
            for m in self.models:
                m_resps = [r for r in s_responses if r.model == m]
                if m_resps:
                    m_latencies[m] = round(
                        sum(r.duration_seconds for r in m_resps) / len(m_resps), 1
                    )

            avg_score = sum(g.percentage for g in s_grades) / len(s_grades) if s_grades else 0.0
            server_bias = (
                round(avg_score - global_avg_score, 2)
                if (s_grades and global_avg_score > 0)
                else 0.0
            )

            summaries.append(
                ServerBenchmarkSummary(
                    server=s_url,
                    generation_duration_avg=round(gen_avg, 2),
                    total_duration_seconds=round(total_dur, 2),
                    tasks_generated_count=len(s_responses),
                    evaluations_performed_count=len(s_grades),
                    avg_score_awarded=round(avg_score, 1),
                    server_score_bias=server_bias,
                    model_latencies=m_latencies,
                )
            )

        summaries.sort(key=lambda s: s.generation_duration_avg)
        return summaries

    def _save_report(self, report: BenchmarkReport) -> Path:
        """Persist structured benchmark report to JSON artifact."""
        out_dir = CONST_DATA_DIR / "benchmarks"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{report.session_id}-benchmark.json"
        out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved benchmark report to %s", out_path)
        return out_path

    def render_results(self, report: BenchmarkReport) -> None:
        """Print rich summary tables and leaderboards to console."""
        table = Table(
            title=f"AI Benchmark Leaderboard (Session {report.session_id})",
            header_style="bold magenta",
        )
        table.add_column("Rank", justify="center", style="bold")
        table.add_column("Model", style="cyan")
        table.add_column("Score", justify="right", style="bold green")
        table.add_column("Peer Score", justify="right", style="green")
        table.add_column("Accuracy", justify="right")
        table.add_column("Security", justify="right")
        table.add_column("Complete", justify="right")
        table.add_column("Clarity", justify="right")
        table.add_column("Judge Wt", justify="right", style="magenta")
        table.add_column("Latency", justify="right", style="dim")
        table.add_column("Bias (Judge)", justify="right", style="dim")
        table.add_column("Self-Bias", justify="right", style="yellow")

        for idx, m in enumerate(report.leaderboard, start=1):
            rank_badge = (
                "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"#{idx}"))
            )
            bias_str = (
                f"+{m.grading_strictness_index:.1f}%"
                if m.grading_strictness_index > 0
                else f"{m.grading_strictness_index:.1f}%"
            )
            self_bias_str = (
                f"+{m.self_preference_bias:.1f}%"
                if m.self_preference_bias > 0
                else f"{m.self_preference_bias:.1f}%"
            )
            table.add_row(
                rank_badge,
                m.model,
                f"{m.overall_percentage:.1f}%",
                f"{m.peer_only_percentage:.1f}%",
                f"{m.accuracy_avg:.1f}/10",
                f"{m.security_avg:.1f}/10",
                f"{m.completeness_avg:.1f}/10",
                f"{m.clarity_avg:.1f}/10",
                f"{m.judge_weight:.2f}",
                f"{m.average_duration_seconds:.1f}s",
                bias_str,
                self_bias_str,
            )

        report_path = CONST_DATA_DIR / "benchmarks" / f"{report.session_id}-benchmark.json"
        console.print()
        console.print(table)

        if len(report.tasks_run) > 1:
            categories = sorted({t.category for t in report.tasks_run})
            cat_table = Table(
                title=f"Domain Category Breakdown (Session {report.session_id})",
                header_style="bold cyan",
            )
            cat_table.add_column("Model", style="cyan")
            for cat in categories:
                cat_table.add_column(cat.capitalize(), justify="right")

            for m in report.leaderboard:
                row = [m.model]
                for cat in categories:
                    score = m.category_scores.get(cat, 0.0)
                    row.append(f"{score:.1f}%")
                cat_table.add_row(*row)

            console.print()
            console.print(cat_table)

        if report.server_benchmarks:
            server_table = Table(
                title=f"Ollama Server Hardware & Node Performance (Session {report.session_id})",
                header_style="bold green",
            )
            server_table.add_column("Server / Worker Node", style="cyan")
            server_table.add_column("Avg Latency", justify="right", style="bold yellow")
            server_table.add_column("Total Time", justify="right", style="dim")
            server_table.add_column("Tasks", justify="right", style="dim")
            server_table.add_column("Avg Score Given", justify="right", style="magenta")
            server_table.add_column("Server Bias", justify="right")
            server_table.add_column("Per-Model Latency Breakdown", style="dim")

            for s in report.server_benchmarks:
                bias_str = (
                    f"+{s.server_score_bias:.1f}%"
                    if s.server_score_bias > 0
                    else f"{s.server_score_bias:.1f}%"
                )
                lat_breakdown = ", ".join(
                    f"{m.split(':')[0]}: {dur}s" for m, dur in s.model_latencies.items()
                )
                server_table.add_row(
                    s.server,
                    f"{s.generation_duration_avg:.1f}s",
                    f"{s.total_duration_seconds:.1f}s",
                    str(s.tasks_generated_count),
                    f"{s.avg_score_awarded:.1f}%",
                    bias_str,
                    lat_breakdown or "-",
                )

            console.print()
            console.print(server_table)

        rprint(f"\n[dim]✓ Detailed benchmark report saved → [/dim][cyan]{report_path}[/cyan]\n")

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
                f"{m.peer_only_percentage:.1f}% | {m.accuracy_avg:.1f}/10 | "
                f"{m.security_avg:.1f}/10 | {m.completeness_avg:.1f}/10 | "
                f"{m.clarity_avg:.1f}/10 | {m.judge_weight:.2f} | "
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
                "| Server / Worker | Avg Latency | Total Time | Tasks | "
                "Avg Score Given | Server Bias | Per-Model Latencies |"
            )
            lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
            for s in report.server_benchmarks:
                bias_str = (
                    f"+{s.server_score_bias:.1f}%"
                    if s.server_score_bias > 0
                    else f"{s.server_score_bias:.1f}%"
                )
                lat_breakdown = ", ".join(
                    f"{m.split(':')[0]}: {dur}s" for m, dur in s.model_latencies.items()
                )
                lines.append(
                    f"| `{s.server}` | {s.generation_duration_avg:.1f}s | "
                    f"{s.total_duration_seconds:.1f}s | {s.tasks_generated_count} | "
                    f"{s.avg_score_awarded:.1f}% | {bias_str} | {lat_breakdown or '-'} |"
                )

        if report.peer_grades:
            lines.append("\n## Model Strengths & Improvement Areas (Peer Feedback)\n")
            for m in report.leaderboard:
                lines.append(
                    f"### `{m.model}` ({m.overall_percentage:.1f}% Score | "
                    f"{m.average_duration_seconds:.1f}s Latency)\n"
                )
                m_grades = [
                    g
                    for g in report.peer_grades
                    if g.candidate_model == m.model and g.evaluator_model != m.model
                ]
                if not m_grades:
                    m_grades = [g for g in report.peer_grades if g.candidate_model == m.model]

                all_s: list[str] = []
                all_w: list[str] = []
                for g in m_grades:
                    all_s.extend(g.strengths)
                    all_w.extend(g.weaknesses)

                top_s: list[str] = []
                seen_s: set[str] = set()
                for str_item in all_s:
                    if str_item and str_item not in seen_s:
                        seen_s.add(str_item)
                        top_s.append(str_item)
                        if len(top_s) >= 3:
                            break

                top_w: list[str] = []
                seen_w: set[str] = set()
                for w_item in all_w:
                    if w_item and w_item not in seen_w:
                        seen_w.add(w_item)
                        top_w.append(w_item)
                        if len(top_w) >= 3:
                            break

                lines.append("**Key Strengths:**")
                if top_s:
                    for str_item in top_s:
                        lines.append(f"- {str_item}")
                else:
                    lines.append("- Baseline responses provided.")

                lines.append("\n**Key Improvement Areas:**")
                if top_w:
                    for w_item in top_w:
                        lines.append(f"- {w_item}")
                else:
                    lines.append("- No major deficiencies noted.")
                lines.append("")

        return "\n".join(lines)
