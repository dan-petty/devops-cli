"""Multi-model LLM benchmark evaluation harness suite grounded in feedback datasets."""

from __future__ import annotations

import ast
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.client import LLMClient
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.settings import Settings, get_ai_api_key, load_settings
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.dry_run.state import is_dry_run
from devops_cli.exceptions import SecurityError
from devops_cli.models.benchmark import (
    BenchmarkSuiteCase,
    BenchmarkSuiteEvaluation,
    BenchmarkSuiteReport,
    ModelSuiteMetrics,
)
from devops_cli.output import (
    format_benchmark_suite_table,
    format_duration,
    print_info,
)
from devops_cli.security.complexity import _ComplexityVisitor

logger = logging.getLogger(__name__)

_RANK_BADGES: dict[int, str] = {1: "🥇", 2: "🥈", 3: "🥉"}
_SUITE_SYSTEM_PROMPT: str = load_task_prompt("benchmark_suite_system.md").strip()
_SUITE_USER_PROMPT_TEMPLATE: str = load_task_prompt("benchmark_suite_user.md").strip()


def _get_rank_badge(rank: int) -> str:
    """Return medal icon or numeric rank badge."""
    return _RANK_BADGES.get(rank, f"#{rank}")


def _resolve_suite_dataset_path(dataset_path: Path | None) -> Path:
    """Safely validate and resolve feedback dataset JSONL path."""
    top_root = find_top_level_repo_root(Path.cwd())
    if dataset_path is None:
        settings = load_settings()
        ds = settings.data.feedback_dataset_path
        target_path = ds if ds.is_absolute() else (top_root / ds)
    else:
        target_path = dataset_path if dataset_path.is_absolute() else (top_root / dataset_path)

    if target_path.is_symlink():
        raise SecurityError(f"dataset_path must not be a symbolic link: {target_path}")

    resolved = target_path.resolve()
    import tempfile

    allowed_roots = [
        top_root.resolve(),
        Path.cwd().resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    if dataset_path is not None and not any(resolved.is_relative_to(r) for r in allowed_roots):
        raise SecurityError(f"dataset_path escapes allowed workspace directories: {resolved}")
    return resolved


def _get_str_field(data: dict[str, Any], key: str, default: str = "") -> str:
    """Extract string value with fallback default."""
    val = data.get(key)
    return str(val) if val is not None else default


def _determine_is_vulnerability(data: dict[str, Any], status: str) -> bool:
    """Determine ground-truth vulnerability presence."""
    if status in ("VALIDATED", "VERIFIED"):
        return True
    return bool(data.get("verified", False))


def _parse_feedback_record_to_case(data: dict[str, Any], index: int) -> BenchmarkSuiteCase | None:
    """Convert raw feedback json record to BenchmarkSuiteCase."""
    title = str(data.get("title") or "").strip()
    if not title:
        return None
    raw_status = str(data.get("status") or "INVALIDATED").upper()
    case_id = str(data.get("id") or data.get("session_id") or f"case-{index}")
    return BenchmarkSuiteCase(
        case_id=case_id,
        persona=_get_str_field(data, "persona", "devsecops"),
        title=title,
        severity=_get_str_field(data, "severity", "medium"),
        location=_get_str_field(data, "location", ""),
        description=_get_str_field(data, "description", ""),
        code_snippet=str(data.get("code_snippet") or data.get("fix", "")),
        ground_truth_status=raw_status,
        is_vulnerability=_determine_is_vulnerability(data, raw_status),
        invalidation_reason=data.get("invalidation_reason"),
        expected_finding=data.get("expected_finding") or title,
    )


def _read_dataset_file(path: Path) -> list[BenchmarkSuiteCase]:
    """Parse JSONL file into list of BenchmarkSuiteCase items."""
    cases: list[BenchmarkSuiteCase] = []
    try:
        content = path.read_text(encoding="utf-8")
        for idx, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                case = _parse_feedback_record_to_case(rec, idx)
                if case is not None:
                    cases.append(case)
            except Exception:
                continue
    except Exception as exc:
        logger.debug("Failed reading dataset file %s: %s", path, exc)
    return cases


def get_baseline_suite_cases() -> list[BenchmarkSuiteCase]:
    """Provide reference baseline evaluation suite cases grounded in repository findings."""
    return [
        BenchmarkSuiteCase(
            case_id="sec-ssrf-webhook-fetch",
            persona="devsecops",
            title="SSRF in Webhook Dispatcher via Unvalidated Destination URL",
            severity="critical",
            location="src/devops_cli/ai/common_tools.py:L45",
            description="HTTP client retrieves remote URLs without validating loopback, link-local, or private IP ranges.",
            code_snippet=(
                "async def fetch_webhook(target_url: str) -> str:\n"
                "    async with httpx2.AsyncClient() as client:\n"
                "        resp = await client.get(target_url)\n"
                "        return resp.text\n"
            ),
            ground_truth_status="VALIDATED",
            is_vulnerability=True,
            expected_finding="Server-Side Request Forgery (SSRF) vulnerability",
        ),
        BenchmarkSuiteCase(
            case_id="sec-hardcoded-api-secret",
            persona="devsecops",
            title="Hardcoded Production API Secret Key in Config",
            severity="high",
            location="src/devops_cli/config/defaults.py:L12",
            description="Static credentials stored directly in production source code.",
            code_snippet=(
                "API_ACCESS_KEY_ID = '<masked-api-access-key-id>'\n"
                "API_SECRET_KEY = '<masked-api-secret-key-token>'\n"
            ),
            ground_truth_status="VALIDATED",
            is_vulnerability=True,
            expected_finding="Hardcoded credential leak",
        ),
        BenchmarkSuiteCase(
            case_id="sec-subprocess-shell-true",
            persona="devsecops",
            title="Arbitrary Command Execution via shell=True Subprocess",
            severity="high",
            location="src/devops_cli/core/executor.py:L33",
            description="User provided repository path formatted directly into shell command.",
            code_snippet=(
                "def run_git_summary(repo_path: str) -> str:\n"
                "    cmd = f'git status {repo_path}'\n"
                "    return subprocess.check_output(cmd, shell=True).decode()\n"
            ),
            ground_truth_status="VALIDATED",
            is_vulnerability=True,
            expected_finding="Subprocess shell injection",
        ),
        BenchmarkSuiteCase(
            case_id="qa-pep758-bracketless-except",
            persona="qa",
            title="Unparenthesized Exception Tuple SyntaxError Hallucination",
            severity="medium",
            location="src/devops_cli/core/pipeline.py:L88",
            description="Python 3.14 PEP 758 valid unparenthesized except clause flagged as invalid syntax.",
            code_snippet=(
                "try:\n"
                "    payload = json.loads(raw_data)\n"
                "except ValueError, TypeError as err:\n"
                "    logger.warning('Failed to parse payload: %s', err)\n"
            ),
            ground_truth_status="INVALIDATED",
            is_vulnerability=False,
            invalidation_reason="PEP 758 valid bracketless syntax in Python 3.14+",
        ),
        BenchmarkSuiteCase(
            case_id="qa-masked-secret-placeholder",
            persona="devsecops",
            title="Masked Secret Placeholder Flagged as Active Token",
            severity="low",
            location="docs/README.md:L55",
            description="Example documentation containing sanitized masked string <masked-token>.",
            code_snippet="export DEVOPS_CLI_TOKEN='<masked-bearer-token>'\n",
            ground_truth_status="INVALIDATED",
            is_vulnerability=False,
            invalidation_reason="Sanitized placeholder pattern rather than active credential",
        ),
        BenchmarkSuiteCase(
            case_id="arch-cyclomatic-complexity-cap",
            persona="architecture",
            title="Excessive Cyclomatic Complexity and Indentation Depth",
            severity="medium",
            location="src/devops_cli/ai/parser.py:L210",
            description="Procedural dispatcher exceeding cyclomatic complexity 10 and nesting depth 5.",
            code_snippet=(
                "def process_deep_tree(node, depth=0):\n"
                "    if node.is_valid:\n"
                "        for child in node.children:\n"
                "            if child.active:\n"
                "                while child.has_more():\n"
                "                    if child.flag:\n"
                "                        for item in child.items:\n"
                "                            if item.kind == 1:\n"
                "                                item.save()\n"
            ),
            ground_truth_status="VALIDATED",
            is_vulnerability=True,
            expected_finding="Architectural invariant violation (complexity > 10, nesting > 5)",
        ),
        BenchmarkSuiteCase(
            case_id="arch-clean-functional-pipeline",
            persona="architecture",
            title="Pure Predicate Functional Pipeline Flagged as Complexity Defect",
            severity="low",
            location="src/devops_cli/core/filter.py:L40",
            description="Single-responsibility functional filter mistakenly flagged for refactoring.",
            code_snippet=(
                "def filter_valid_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:\n"
                "    return [item for item in items if item.get('enabled') and item.get('count', 0) > 0]\n"
            ),
            ground_truth_status="INVALIDATED",
            is_vulnerability=False,
            invalidation_reason="Standard declarative list comprehension with cyclomatic complexity <= 3",
        ),
        BenchmarkSuiteCase(
            case_id="qa-docstring-antipattern-example",
            persona="qa",
            title="Docstring Anti-Pattern Demonstration Flagged as Live Defect",
            severity="low",
            location="src/devops_cli/security/sanitizer.py:L15",
            description="Example code illustrating what NOT to do inside markdown docstring.",
            code_snippet=(
                "def sanitize_input(val: str) -> str:\n"
                '    """\n'
                "    Anti-pattern to avoid:\n"
                "    eval(val) # NEVER do this!\n"
                '    """\n'
                "    return val.strip()\n"
            ),
            ground_truth_status="INVALIDATED",
            is_vulnerability=False,
            invalidation_reason="Docstring non-executable comment example",
        ),
    ]


def load_feedback_benchmark_dataset(dataset_path: Path | None = None) -> list[BenchmarkSuiteCase]:
    """Load evaluation test cases from JSONL feedback dataset or baseline reference suite."""
    resolved_path = _resolve_suite_dataset_path(dataset_path)
    if resolved_path.exists() and resolved_path.is_file():
        cases = _read_dataset_file(resolved_path)
        if cases:
            return cases
    return get_baseline_suite_cases()


def evaluate_architectural_compliance(
    code: str, max_complexity: int = 10, max_nesting: int = 5
) -> tuple[int, int, bool]:
    """Evaluate cyclomatic complexity and nesting depth of Python code snippet."""
    clean_code = code.strip()
    if not clean_code:
        return 1, 0, True
    try:
        tree = ast.parse(clean_code)
    except Exception:
        return 0, 0, False

    visitor = _ComplexityVisitor()
    visitor.visit(tree)
    if not visitor.functions:
        return 1, 0, True

    max_comp = max(f.cyclomatic_complexity for f in visitor.functions)
    max_nest = max(f.max_nesting_depth for f in visitor.functions)
    compliant = (max_comp <= max_complexity) and (max_nest <= max_nesting)
    return max_comp, max_nest, compliant


def extract_code_from_response(response_text: str) -> str | None:
    """Extract first fenced Python code block from markdown response."""
    m = re.search(r"```(?:python)?\s*([\s\S]*?)```", response_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _compute_confusion_counts(
    evaluations: list[BenchmarkSuiteEvaluation],
) -> tuple[int, int, int, int]:
    """Tally true positives, false positives, true negatives, and false negatives."""
    tp = sum(1 for e in evaluations if e.is_true_positive)
    fp = sum(1 for e in evaluations if e.is_false_positive)
    tn = sum(1 for e in evaluations if e.is_true_negative)
    fn = sum(1 for e in evaluations if e.is_false_negative)
    return tp, fp, tn, fn


def _compute_prec_rec_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Calculate precision, recall, and harmonic F1 score."""
    total_pos = tp + fp
    total_act = tp + fn
    prec = (tp / total_pos) if total_pos > 0 else (1.0 if total_pos == 0 else 0.0)
    rec = (tp / total_act) if total_act > 0 else (1.0 if total_act == 0 else 0.0)
    denom = prec + rec
    f1 = (2.0 * prec * rec / denom) if denom > 0 else 0.0
    return prec, rec, f1


def _compute_composite_score(
    f1: float,
    hallucination_rate: float,
    compliance_rate: float,
    tokens_per_sec: float,
) -> float:
    """Compute overall score directly from standard F1 score."""
    return round(f1 * 100.0, 2)


def calculate_suite_metrics(
    evaluations: list[BenchmarkSuiteEvaluation],
    model: str,
    provider: str = "ollama",
    server: str = "",
) -> ModelSuiteMetrics:
    """Calculate quantitative evaluation metrics (precision, recall, hallucination, throughput)."""
    total = len(evaluations)
    if total == 0:
        return ModelSuiteMetrics(model=model, provider=provider, server=server)

    tp, fp, tn, fn = _compute_confusion_counts(evaluations)
    prec, rec, f1 = _compute_prec_rec_f1(tp, fp, fn)

    negatives = fp + tn
    hallucination_rate = (fp / negatives) if negatives > 0 else 0.0
    accuracy = (tp + tn) / total

    avg_latency = sum(e.latency_ms for e in evaluations) / total
    total_tokens = sum(e.tokens_generated for e in evaluations)
    total_time_sec = sum(e.latency_ms for e in evaluations) / 1000.0
    tokens_per_sec = (total_tokens / total_time_sec) if total_time_sec > 0 else 0.0

    compliant_count = sum(1 for e in evaluations if e.invariant_compliant)
    compliance_rate = compliant_count / total
    overall = _compute_composite_score(f1, hallucination_rate, compliance_rate, tokens_per_sec)

    return ModelSuiteMetrics(
        model=model,
        provider=provider,
        server=server,
        total_cases=total,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1_score=round(f1, 4),
        hallucination_rate=round(hallucination_rate, 4),
        accuracy=round(accuracy, 4),
        avg_latency_ms=round(avg_latency, 2),
        avg_tokens_per_second=round(tokens_per_sec, 2),
        total_tokens=total_tokens,
        architectural_compliance_rate=round(compliance_rate, 4),
        overall_score=round(overall, 2),
    )


def _compute_model_recommendations(leaderboard: list[ModelSuiteMetrics]) -> list[str]:
    """Generate persona allocation recommendations based on metric profiles."""
    if not leaderboard:
        return ["No models evaluated in this suite."]
    recs: list[str] = []
    top_overall = leaderboard[0]
    recs.append(
        f"**Primary Code Review Leader**: `{top_overall.model}` achieved the highest overall score "
        f"({top_overall.overall_score:.1f}%) with {top_overall.precision * 100.0:.1f}% precision and "
        f"{top_overall.f1_score * 100.0:.1f}% F1."
    )

    by_hallucination = sorted(leaderboard, key=lambda m: (m.hallucination_rate, -m.f1_score))
    lowest_hallucination = by_hallucination[0]
    if lowest_hallucination.hallucination_rate <= 0.10:
        recs.append(
            f"**Recommended QA / Invalidation Filter**: `{lowest_hallucination.model}` demonstrated lowest "
            f"hallucination rate ({lowest_hallucination.hallucination_rate * 100.0:.1f}%), ideal for secondary review filtering."
        )

    by_compliance = sorted(
        leaderboard, key=lambda m: (-m.architectural_compliance_rate, -m.overall_score)
    )
    top_compliance = by_compliance[0]
    if top_compliance.architectural_compliance_rate >= 0.90:
        recs.append(
            f"**Recommended Architecture / Refactoring Agent**: `{top_compliance.model}` achieved "
            f"{top_compliance.architectural_compliance_rate * 100.0:.1f}% architectural compliance, "
            f"consistently satisfying complexity <= 10 and nesting <= 5."
        )
    return recs


def _parse_verdict_from_response(response_text: str) -> tuple[bool, float, str | None]:
    """Parse vulnerability verdict, confidence, and code fix from response."""
    verdict_match = re.search(
        r"^\s*VERDICT:\s*(VULNERABILITY(?:\s+DETECTED)?|FALSE[_\s]POSITIVE|CLEAN)",
        response_text,
        re.MULTILINE | re.IGNORECASE,
    )
    if verdict_match:
        tag = verdict_match.group(1).upper()
        predicted = "VULNERABILITY" in tag
    else:
        has_fp = bool(
            re.search(
                r"\b(?:FALSE[_\s]POSITIVE|NOT\s+A\s+VULNERABILITY|NO\s+VULNERABILITY)\b",
                response_text,
                re.IGNORECASE,
            )
        )
        has_tp = bool(
            re.search(
                r"\b(?:VULNERABILITY\s+DETECTED|TRUE\s+POSITIVE|SECURITY\s+VULNERABILITY|DEFECT\s+CONFIRMED)\b",
                response_text,
                re.IGNORECASE,
            )
        )
        predicted = has_tp and not has_fp

    conf_match = re.search(r"confidence[:\s]+([0-9.]+)", response_text, re.IGNORECASE)
    conf = float(conf_match.group(1)) if conf_match else 0.0
    conf = max(0.0, min(1.0, conf))

    code = extract_code_from_response(response_text)
    return predicted, conf, code


def _simulate_prediction(model: str, is_vulnerability: bool) -> bool:
    """Simulate model prediction based on model name and case truth."""
    is_weak = any(k in model.lower() for k in ("weak", "tiny"))
    if is_weak:
        return not is_vulnerability
    return is_vulnerability


def _format_markdown_leaderboard_row(rank: int, m: ModelSuiteMetrics) -> str:
    """Format single model row for markdown leaderboard."""
    badge = _get_rank_badge(rank)
    return (
        f"| {badge} | `{m.model}` | **{m.overall_score:.1f}%** | {m.precision * 100.0:.1f}% | "
        f"{m.recall * 100.0:.1f}% | {m.f1_score * 100.0:.1f}% | {m.hallucination_rate * 100.0:.1f}% | "
        f"{m.architectural_compliance_rate * 100.0:.1f}% | {m.avg_latency_ms:.1f}ms | {m.avg_tokens_per_second:.1f} tps |"
    )


def _get_eval_outcome(ev: BenchmarkSuiteEvaluation) -> str:
    """Return two-letter confusion matrix classification."""
    if ev.is_true_positive:
        return "TP"
    if ev.is_false_positive:
        return "FP"
    if ev.is_true_negative:
        return "TN"
    return "FN"


class BenchmarkSuiteRunner:
    """Orchestrates multi-model benchmark evaluations against feedback datasets."""

    def __init__(
        self,
        models: list[str],
        dataset_path: Path | None = None,
        settings: Settings | None = None,
        provider: str | None = None,
        is_dry_run: bool | None = None,
        concurrency: int = 4,
        servers: list[str] | None = None,
        quiet: bool = False,
    ) -> None:
        self.models = models or ["qwen2.5-coder:7b"]
        self.dataset_path = dataset_path
        self.settings = settings or load_settings()
        self.provider = provider or self.settings.ai.provider
        self.session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._is_dry_run_override = is_dry_run
        self.servers = servers or self.settings.ai.ollama_urls or ["http://localhost:11434"]
        self.concurrency = max(1, concurrency)
        self.quiet = quiet
        self._print_lock = threading.Lock()

    def _client_for_model(self, model_name: str, server_url: str | None = None) -> LLMClient:
        """Instantiate LLMClient for candidate model and server endpoint."""
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

    def _simulate_case_evaluation(
        self,
        model: str,
        case: BenchmarkSuiteCase,
        server_url: str | None,
    ) -> BenchmarkSuiteEvaluation:
        """Simulate realistic evaluation outcome deterministically in dry-run mode."""
        predicted = _simulate_prediction(model, case.is_vulnerability)
        is_tp = predicted and case.is_vulnerability
        is_fp = predicted and not case.is_vulnerability
        is_tn = not predicted and not case.is_vulnerability
        is_fn = not predicted and case.is_vulnerability

        sim_code = (
            "def safe_remediation(target: str) -> str:\n"
            "    # Clean single-responsibility helper compliant with invariants\n"
            "    return target.strip()\n"
        )
        max_comp, max_nest, compliant = evaluate_architectural_compliance(sim_code)

        return BenchmarkSuiteEvaluation(
            model=model,
            case_id=case.case_id,
            persona=case.persona,
            predicted_vulnerability=predicted,
            confidence_score=0.92 if "weak" not in model.lower() else 0.65,
            model_output=f"[Simulated {model} Evaluation for {case.case_id}] Predicted: {predicted}",
            generated_code=sim_code,
            is_true_positive=is_tp,
            is_false_positive=is_fp,
            is_true_negative=is_tn,
            is_false_negative=is_fn,
            complexity_score=max_comp,
            nesting_depth=max_nest,
            invariant_compliant=compliant,
            latency_ms=75.0,
            tokens_generated=120,
            tokens_per_second=160.0,
        )

    def _live_case_evaluation(
        self,
        model: str,
        case: BenchmarkSuiteCase,
        server_url: str | None,
    ) -> BenchmarkSuiteEvaluation:
        """Execute real LLM call against evaluation case and calculate scores."""
        client = self._client_for_model(model, server_url)
        prompt = _SUITE_USER_PROMPT_TEMPLATE.format(
            persona=case.persona,
            title=case.title,
            location=case.location,
            code_snippet=case.code_snippet,
        )
        system_prompt = _SUITE_SYSTEM_PROMPT
        start_time = time.perf_counter()
        try:
            resp = client.chat(system=system_prompt, user=prompt)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            resp_text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            resp_text = f"Error during model evaluation: {exc}"

        predicted, conf, code = _parse_verdict_from_response(resp_text)
        is_tp = predicted and case.is_vulnerability
        is_fp = predicted and not case.is_vulnerability
        is_tn = not predicted and not case.is_vulnerability
        is_fn = not predicted and case.is_vulnerability

        max_comp, max_nest, compliant = evaluate_architectural_compliance(code or "")
        token_count = max(1, len(resp_text.split()))
        elapsed_sec = elapsed_ms / 1000.0
        tps = (token_count / elapsed_sec) if elapsed_sec > 0 else 0.0

        return BenchmarkSuiteEvaluation(
            model=model,
            case_id=case.case_id,
            persona=case.persona,
            predicted_vulnerability=predicted,
            confidence_score=conf,
            model_output=resp_text,
            generated_code=code,
            is_true_positive=is_tp,
            is_false_positive=is_fp,
            is_true_negative=is_tn,
            is_false_negative=is_fn,
            complexity_score=max_comp,
            nesting_depth=max_nest,
            invariant_compliant=compliant,
            latency_ms=elapsed_ms,
            tokens_generated=token_count,
            tokens_per_second=tps,
        )

    def _evaluate_single_case(
        self,
        model: str,
        case: BenchmarkSuiteCase,
        dry_run: bool,
        server_url: str | None,
    ) -> BenchmarkSuiteEvaluation:
        """Route case evaluation to simulator or live client."""
        if dry_run:
            return self._simulate_case_evaluation(model, case, server_url)
        return self._live_case_evaluation(model, case, server_url)

    def _evaluate_model_cases(
        self,
        model: str,
        cases: list[BenchmarkSuiteCase],
        dry_run: bool,
        server_url: str | None,
    ) -> tuple[ModelSuiteMetrics, list[BenchmarkSuiteEvaluation]]:
        """Evaluate all cases for a single model and compute aggregate metrics."""
        evals: list[BenchmarkSuiteEvaluation] = []
        for case in cases:
            ev = self._evaluate_single_case(model, case, dry_run, server_url)
            evals.append(ev)
        metrics = calculate_suite_metrics(
            evaluations=evals,
            model=model,
            provider=self.provider,
            server=server_url or "",
        )
        return metrics, evals

    def _save_report(self, report: BenchmarkSuiteReport) -> Path:
        """Save benchmark suite report to local benchmarks data directory."""
        from devops_cli.ai.benchmark.runner import _get_benchmarks_base_dir

        base_dir = _get_benchmarks_base_dir()
        out_file = base_dir / f"suite-{report.session_id}.json"
        out_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return out_file

    def to_markdown(self, report: BenchmarkSuiteReport) -> str:
        """Format complete benchmark suite report into structured Markdown."""
        lines = [
            f"# AI Benchmark Evaluation Suite Report (Session `{report.session_id}`)\n",
            f"- **Date**: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- **Total Test Cases**: {report.total_cases}",
            f"- **Dataset Source**: `{report.dataset_path or 'baseline reference dataset'}`",
            f"- **Dry Run Mode**: `{'Yes' if report.is_dry_run else 'No'}`\n",
            "## 🏆 Leaderboard Summary\n",
            "| Rank | Model | Overall Score | Precision | Recall | F1 Score | Hallucination Rate | Arch Compliance | Latency | Throughput |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for rank, m in enumerate(report.leaderboard, start=1):
            lines.append(_format_markdown_leaderboard_row(rank, m))

        lines.append("\n## 💡 Persona Recommendations\n")
        for rec in report.recommendations:
            lines.append(f"- {rec}")

        lines.append("\n## 📊 Detailed Metric Breakdown per Candidate Model\n")
        for m in report.leaderboard:
            m_evals = [e for e in report.evaluations if e.model == m.model]
            lines.extend(
                [
                    f"### `{m.model}` ({m.overall_score:.1f}% Composite Score)\n",
                    f"- **True Positives**: {m.true_positives} | **False Positives**: {m.false_positives}",
                    f"- **True Negatives**: {m.true_negatives} | **False Negatives**: {m.false_negatives}",
                    f"- **Average Inference Latency**: {format_duration(m.avg_latency_ms / 1000.0)}",
                    f"- **Token Throughput**: {m.avg_tokens_per_second:.1f} tokens/sec ({m.total_tokens} tokens total)",
                    f"- **Architectural Compliance**: {m.architectural_compliance_rate * 100.0:.1f}% (complexity <= 10, nesting <= 5)\n",
                ]
            )
            if m_evals:
                lines.append("**Evaluated Test Cases:**")
                for ev in m_evals:
                    status_icon = "✅" if (ev.is_true_positive or ev.is_true_negative) else "❌"
                    outcome = _get_eval_outcome(ev)
                    lines.append(
                        f"- {status_icon} `{ev.case_id}`: **{outcome}** (Predicted Vuln: `{ev.predicted_vulnerability}`, Conf: {ev.confidence_score:.2f})"
                    )
                lines.append("")
        return "\n".join(lines)

    def render_results(self, report: BenchmarkSuiteReport) -> None:
        """Render Rich terminal comparison tables to stdout."""
        from devops_cli.output import print as print_out

        print_out(format_benchmark_suite_table(report))
        if report.recommendations:
            print_info("\n[bold]Persona & Task Offloading Recommendations:[/bold]", prefix=False)
            for r in report.recommendations:
                print_info(f"  • {r}", prefix=False)

    def _execute_model_evaluations(
        self, cases: list[BenchmarkSuiteCase], dry_run: bool
    ) -> tuple[list[ModelSuiteMetrics], list[BenchmarkSuiteEvaluation]]:
        """Evaluate all candidate models sequentially or concurrently."""
        leaderboard: list[ModelSuiteMetrics] = []
        all_evaluations: list[BenchmarkSuiteEvaluation] = []

        num_workers = min(self.concurrency, len(self.models))
        if num_workers > 1:
            with ThreadPoolExecutor(max_workers=num_workers) as pool:
                futures = {
                    pool.submit(
                        self._evaluate_model_cases,
                        m,
                        cases,
                        dry_run,
                        self.servers[idx % len(self.servers)] if self.servers else None,
                    ): m
                    for idx, m in enumerate(self.models)
                }
                for f in as_completed(futures):
                    metrics, evals = f.result()
                    leaderboard.append(metrics)
                    all_evaluations.extend(evals)
        else:
            for idx, m in enumerate(self.models):
                s_url = self.servers[idx % len(self.servers)] if self.servers else None
                metrics, evals = self._evaluate_model_cases(m, cases, dry_run, s_url)
                leaderboard.append(metrics)
                all_evaluations.extend(evals)

        return leaderboard, all_evaluations

    def run(self) -> BenchmarkSuiteReport:
        """Execute full benchmark evaluation suite across candidate models."""
        dry_run = (
            self._is_dry_run_override if self._is_dry_run_override is not None else is_dry_run()
        )
        cases = load_feedback_benchmark_dataset(self.dataset_path)

        if not self.quiet:
            print_info(
                f"\n[bold blue]=== Starting AI Model Evaluation Suite (Session {self.session_id}) ===[/bold blue]",
                prefix=False,
            )
            print_info(
                f"[dim]Models: {len(self.models)} | Evaluation Cases: {len(cases)} | "
                f"Dataset: {self.dataset_path or 'baseline feedback'} | Dry Run: {dry_run}[/dim]\n",
                prefix=False,
            )

        leaderboard, all_evaluations = self._execute_model_evaluations(cases, dry_run)
        leaderboard.sort(key=lambda x: x.overall_score, reverse=True)
        recommendations = _compute_model_recommendations(leaderboard)

        report = BenchmarkSuiteReport(
            session_id=self.session_id,
            dataset_path=str(self.dataset_path or ".data/feedback_dataset.jsonl"),
            total_cases=len(cases),
            models_evaluated=self.models,
            leaderboard=leaderboard,
            evaluations=all_evaluations,
            recommendations=recommendations,
            is_dry_run=dry_run,
        )

        self._save_report(report)
        return report
