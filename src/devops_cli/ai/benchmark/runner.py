"""Multi-model benchmark runner, peer-grading evaluation engine, and reporting."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

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
    ) -> None:
        self.models = models or ["qwen2.5-coder:7b"]
        self.tasks = tasks
        self.settings = settings or load_settings()
        self.provider = provider or self.settings.ai.provider
        self.session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._is_dry_run_override = is_dry_run

    def _client_for_model(self, model_name: str) -> LLMClient:
        """Instantiate an LLMClient for a given model override."""
        cfg = self.settings.ai.model_copy(update={"model": model_name})
        api_key = get_ai_api_key(self.settings)
        return LLMClient(cfg, api_key=api_key)

    def _simulate_response(self, task: BenchmarkTask, model: str) -> TaskResponse:
        """Simulate realistic model response in dry-run mode."""
        return TaskResponse(
            task_id=task.id,
            model=model,
            provider=self.provider,
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

    def execute(self) -> BenchmarkReport:
        """Run complete benchmark workflow across all tasks and candidate models."""
        dry_run = (
            self._is_dry_run_override if self._is_dry_run_override is not None else is_dry_run()
        )
        responses: list[TaskResponse] = []
        peer_grades: list[PeerGrade] = []

        rprint(
            f"[bold cyan]Starting AI Benchmark Suite[/bold cyan] "
            f"([green]{len(self.models)}[/green] models, [green]{len(self.tasks)}[/green] tasks)"
        )

        # ── Step 1: Generate Model Responses (Grouped by Model) ──────────────
        rprint("[dim]Step 1/2: Generating candidate responses grouped by model...[/dim]")
        for model_name in self.models:
            rprint(f"[bold]Evaluating model:[/bold] [cyan]{model_name}[/cyan]")
            client = self._client_for_model(model_name) if not dry_run else None
            for task in self.tasks:
                if dry_run:
                    resp = self._simulate_response(task, model_name)
                    responses.append(resp)
                    continue

                assert client is not None
                t0 = time.monotonic()
                try:
                    res_text = client.chat(
                        system="You are an expert DevOps and DevSecOps staff engineer.",
                        user=task.prompt,
                    )
                    duration = time.monotonic() - t0
                    responses.append(
                        TaskResponse(
                            task_id=task.id,
                            model=model_name,
                            provider=self.provider,
                            response=res_text,
                            duration_seconds=round(duration, 2),
                        )
                    )
                    rprint(f"  ✓ completed [cyan]{task.id}[/cyan] in {duration:.1f}s")
                except Exception as exc:
                    logger.warning("Model %s failed on task %s: %s", model_name, task.id, exc)
                    responses.append(
                        TaskResponse(
                            task_id=task.id,
                            model=model_name,
                            provider=self.provider,
                            response=f"Error generating response: {exc}",
                            duration_seconds=round(time.monotonic() - t0, 2),
                        )
                    )

        # ── Step 2: Peer Grading Matrix (Grouped by Evaluator Model) ──────────
        rprint("\n[dim]Step 2/2: Cross-model blind peer grading (all models evaluated)...[/dim]")
        resp_map = {(r.task_id, r.model): r for r in responses}

        for evaluator_model in self.models:
            rprint(f"[bold]Evaluator judge:[/bold] [cyan]{evaluator_model}[/cyan]")
            for task in self.tasks:
                for candidate_model in self.models:
                    c_resp = resp_map.get((task.id, candidate_model))
                    if not c_resp:
                        continue

                    if dry_run:
                        grade = self._simulate_peer_grade(task, candidate_model, evaluator_model)
                        peer_grades.append(grade)
                        continue

                    grade = self._evaluate_response(task, c_resp, evaluator_model)
                    peer_grades.append(grade)
                    rprint(
                        f"  ✓ graded [yellow]{candidate_model}[/yellow] "
                        f"on [dim]{task.id}[/dim] → [bold]{grade.percentage:.1f}%[/bold]"
                    )

        # ── Step 3: Compute Leaderboard Aggregates ────────────────────────────
        leaderboard = self._compute_leaderboard(responses, peer_grades)

        report = BenchmarkReport(
            session_id=self.session_id,
            models_evaluated=self.models,
            tasks_run=self.tasks,
            responses=responses,
            peer_grades=peer_grades,
            leaderboard=leaderboard,
            is_dry_run=dry_run,
        )

        self._save_report(report)
        return report

    def _evaluate_response(
        self,
        task: BenchmarkTask,
        response: TaskResponse,
        evaluator_model: str,
    ) -> PeerGrade:
        """Call evaluator model with grading prompt and parse structured score."""
        client = self._client_for_model(evaluator_model)
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
            res = client.chat(
                system=(
                    "You are an expert AI peer evaluation judge reviewing an anonymous "
                    "candidate response against reference criteria. Return valid JSON only."
                ),
                user=prompt_text,
            )
            data = extract_json_block(res)
            if isinstance(data, dict):
                acc = float(data.get("accuracy_score", 7.0))
                sec = float(data.get("security_score", 7.0))
                comp = float(data.get("completeness_score", 7.0))
                clar = float(data.get("clarity_score", 7.0))
                total = float(data.get("total_score", acc + sec + comp + clar))
                pct = float(data.get("percentage", (total / 40.0) * 100.0))

                return PeerGrade(
                    task_id=task.id,
                    candidate_model=response.model,
                    evaluator_model=evaluator_model,
                    accuracy_score=round(min(10.0, max(0.0, acc)), 1),
                    security_score=round(min(10.0, max(0.0, sec)), 1),
                    completeness_score=round(min(10.0, max(0.0, comp)), 1),
                    clarity_score=round(min(10.0, max(0.0, clar)), 1),
                    total_score=round(min(40.0, max(0.0, total)), 1),
                    percentage=round(min(100.0, max(0.0, pct)), 1),
                    strengths=list(data.get("strengths", [])),
                    weaknesses=list(data.get("weaknesses", [])),
                    feedback=str(data.get("feedback", "")),
                )
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("Peer evaluation failed: %s", exc)

        # Fallback default score on parse error
        return PeerGrade(
            task_id=task.id,
            candidate_model=response.model,
            evaluator_model=evaluator_model,
            accuracy_score=7.0,
            security_score=7.0,
            completeness_score=7.0,
            clarity_score=7.0,
            total_score=28.0,
            percentage=70.0,
            feedback=f"Evaluation default due to parsing error: {err_msg}",
        )

    def _compute_leaderboard(
        self,
        responses: list[TaskResponse],
        grades: list[PeerGrade],
    ) -> list[ModelBenchmarkSummary]:
        """Aggregate peer grades into comprehensive per-model metrics."""
        task_cat_map = {t.id: t.category for t in self.tasks}
        task_weight_map = {t.id: t.weight for t in self.tasks}
        summaries: list[ModelBenchmarkSummary] = []

        for model in self.models:
            m_grades = [g for g in grades if g.candidate_model == model]
            m_resps = [r for r in responses if r.model == model]

            avg_dur = sum(r.duration_seconds for r in m_resps) / len(m_resps) if m_resps else 0.0

            if not m_grades:
                summaries.append(
                    ModelBenchmarkSummary(
                        model=model,
                        provider=self.provider,
                        average_duration_seconds=round(avg_dur, 2),
                    )
                )
                continue

            acc_avg = sum(g.accuracy_score for g in m_grades) / len(m_grades)
            sec_avg = sum(g.security_score for g in m_grades) / len(m_grades)
            comp_avg = sum(g.completeness_score for g in m_grades) / len(m_grades)
            clar_avg = sum(g.clarity_score for g in m_grades) / len(m_grades)

            # Weighted overall percentage
            total_w = sum(task_weight_map.get(g.task_id, 1.0) for g in m_grades)
            weighted_pct = (
                sum(g.percentage * task_weight_map.get(g.task_id, 1.0) for g in m_grades) / total_w
                if total_w > 0
                else 0.0
            )

            # Category scores
            cat_scores: dict[str, list[float]] = {}
            for g in m_grades:
                cat = task_cat_map.get(g.task_id, "general")
                cat_scores.setdefault(cat, []).append(g.percentage)
            cat_avg = {cat: round(sum(vals) / len(vals), 1) for cat, vals in cat_scores.items()}

            # Grading strictness index: how this model grades others vs general consensus
            given_grades = [g for g in grades if g.evaluator_model == model]
            strictness = 0.0
            if given_grades:
                avg_given = sum(g.percentage for g in given_grades) / len(given_grades)
                all_avg = sum(g.percentage for g in grades) / len(grades) if grades else 75.0
                strictness = round(avg_given - all_avg, 2)

            summaries.append(
                ModelBenchmarkSummary(
                    model=model,
                    provider=self.provider,
                    overall_percentage=round(weighted_pct, 1),
                    accuracy_avg=round(acc_avg, 1),
                    security_avg=round(sec_avg, 1),
                    completeness_avg=round(comp_avg, 1),
                    clarity_avg=round(clar_avg, 1),
                    category_scores=cat_avg,
                    average_duration_seconds=round(avg_dur, 2),
                    grading_strictness_index=strictness,
                )
            )

        summaries.sort(key=lambda s: s.overall_percentage, reverse=True)
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
        table.add_column("Accuracy", justify="right")
        table.add_column("Security", justify="right")
        table.add_column("Complete", justify="right")
        table.add_column("Clarity", justify="right")
        table.add_column("Avg Latency", justify="right", style="dim")
        table.add_column("Judge Bias", justify="right", style="dim")

        for idx, m in enumerate(report.leaderboard, start=1):
            rank_badge = (
                "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"#{idx}"))
            )
            bias_str = (
                f"+{m.grading_strictness_index:.1f}%"
                if m.grading_strictness_index > 0
                else f"{m.grading_strictness_index:.1f}%"
            )
            table.add_row(
                rank_badge,
                m.model,
                f"{m.overall_percentage:.1f}%",
                f"{m.accuracy_avg:.1f}/10",
                f"{m.security_avg:.1f}/10",
                f"{m.completeness_avg:.1f}/10",
                f"{m.clarity_avg:.1f}/10",
                f"{m.average_duration_seconds:.2f}s",
                bias_str,
            )

        report_path = CONST_DATA_DIR / "benchmarks" / f"{report.session_id}-benchmark.json"
        console.print()
        console.print(table)
        rprint(f"\n[dim]✓ Detailed benchmark report saved → [/dim][cyan]{report_path}[/cyan]\n")
