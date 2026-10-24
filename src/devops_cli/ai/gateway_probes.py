"""Measured per-deployment capability probes and evaluation (#595).

Executes standardized capability probes against gateway deployments to verify
model quality rather than inferring capability from model parameter names.
Scored using deterministic evaluators and pydantic_evals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from devops_cli.ai.response_repair import fix_llm_response
from devops_cli.config.constants import (
    CONST_CAPABILITY_PROBE_CANARY,
    CONST_CAPABILITY_PROBE_NAMES,
    CONST_CAPABILITY_PROBE_PROHIBITION_PREFIX,
    CONST_REVIEW_CHARS_PER_TOKEN,
)

if TYPE_CHECKING:
    from devops_cli.ai.gateway_evaluators import (
        DeepRecallEvaluator,
        ExplicitProhibitionEvaluator,
        JsonAdherenceEvaluator,
        ToolChoiceEvaluator,
    )

__all__ = [
    "CapabilityProbeScore",
    "DeepRecallEvaluator",
    "DeploymentCapabilities",
    "ExplicitProhibitionEvaluator",
    "JsonAdherenceEvaluator",
    "ToolChoiceEvaluator",
    "build_capability_probes",
    "score_deployment_probes",
]

_EVALUATOR_NAMES = frozenset(
    {
        "DeepRecallEvaluator",
        "ExplicitProhibitionEvaluator",
        "JsonAdherenceEvaluator",
        "ToolChoiceEvaluator",
    }
)


def __getattr__(name: str) -> Any:
    """Load evaluator classes lazily on access to keep startup lean."""
    if name in _EVALUATOR_NAMES:
        import devops_cli.ai.gateway_evaluators as evals_mod

        val = getattr(evals_mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_JSON_PROMPT = (
    "List up to one defect in the target code.\n"
    "You must respond with a valid JSON object containing exactly the following five fields:\n"
    '- "file": string\n'
    '- "line": integer\n'
    '- "severity": string\n'
    '- "rule_id": string\n'
    '- "description": string\n\n'
    "Do not include any text before or after the JSON object."
)

_TOOL_PROMPT = (
    "You have access to the following 10 tools:\n"
    "1. read_file(path: str) -> str: Read file contents.\n"
    "2. write_file(path: str, content: str) -> None: Write content to a file.\n"
    "3. list_directory(path: str) -> list[str]: List directory entries.\n"
    "4. search_symbol(name: str) -> list[str]: Search codebase for a symbol definition.\n"
    "5. inspect_ast(path: str) -> str: Parse a Python file and display its AST structure.\n"
    "6. run_linter(path: str) -> list[str]: Run linter on a file.\n"
    "7. run_tests(target: str) -> str: Run pytest on test targets.\n"
    "8. git_diff(commit: str) -> str: View git diff for a commit.\n"
    "9. fetch_url(url: str) -> str: Fetch an HTTP web page.\n"
    "10. explain_finding(finding_id: str) -> str: Explain a code review finding.\n\n"
    "Task: I need to inspect the Abstract Syntax Tree (AST) structure of 'src/engine.py' "
    "to extract class and function nodes. Which tool should be called?\n"
    "Respond with only the tool name."
)

_PROHIBITION_PROMPT = (
    "Provide a concise summary of the principles of automated code review.\n"
    "Strict prohibition: You must NEVER use the word 'security' or 'vulnerability' anywhere "
    "in your response.\n"
    f"You must start your response with the exact prefix: '{CONST_CAPABILITY_PROBE_PROHIBITION_PREFIX}'."
)


def _build_recall_prompt(prompt_tokens: int, max_input_tokens: int | None = None) -> str:
    """Construct deep recall prompt with canary needle positioned at midpoint."""
    margin_tokens = (
        min(prompt_tokens, int(max_input_tokens * 0.9)) if max_input_tokens else prompt_tokens
    )
    target_tokens = max(100, min(margin_tokens, 2048))
    target_chars = int(target_tokens * CONST_REVIEW_CHARS_PER_TOKEN)

    filler_chunk = "def helper_analysis_block() -> None:\n    x = 100\n    y = x + 200\n"
    half_chars = target_chars // 2
    filler_pre = (filler_chunk * (half_chars // len(filler_chunk) + 1))[:half_chars]
    filler_post = filler_pre

    canary_line = (
        f"\n# VERIFICATION NOTE: The secret canary token is {CONST_CAPABILITY_PROBE_CANARY}.\n"
    )
    question = (
        "\nQuestion: What is the secret canary token mentioned in the text? "
        "Reply with only the canary token."
    )
    return f"{filler_pre}{canary_line}{filler_post}{question}"


def build_capability_probes(
    prompt_tokens: int,
    max_input_tokens: int | None = None,
    trials: int = 1,
) -> list[dict[str, Any]]:
    """Build the standard four capability probe specifications for gateway tuning."""
    return [
        {
            "name": "json_adherence",
            "prompt": _JSON_PROMPT,
            "max_tokens": 200,
            "rounds": trials,
        },
        {
            "name": "tool_choice",
            "prompt": _TOOL_PROMPT,
            "max_tokens": 50,
            "rounds": trials,
        },
        {
            "name": "deep_recall",
            "prompt": _build_recall_prompt(prompt_tokens, max_input_tokens),
            "max_tokens": 50,
            "rounds": trials,
        },
        {
            "name": "explicit_prohibition",
            "prompt": _PROHIBITION_PROMPT,
            "max_tokens": 150,
            "rounds": trials,
        },
    ]


class CapabilityProbeScore(BaseModel):
    """Aggregate score for a single capability probe kind across trials."""

    name: str
    trials: int
    passed: int
    repaired: int
    success_rate: float
    details: list[str] = Field(default_factory=list)


class DeploymentCapabilities(BaseModel):
    """Measured capability scores and probe records for a deployment."""

    probed: bool = False
    trials: int = 0
    probes: dict[str, CapabilityProbeScore] = Field(default_factory=dict)
    passed_probes_count: int = 0
    total_probes_count: int = 0
    all_passed: bool = False
    summary_label: str = "unmeasured"

    def model_post_init(self, __context: Any) -> None:
        """Derive counters and labels from probe records."""
        if not self.probed:
            self.passed_probes_count = 0
            self.total_probes_count = len(self.probes)
            self.all_passed = False
            self.summary_label = "unmeasured"
            return

        passed = sum(1 for p in self.probes.values() if p.passed == p.trials and p.trials > 0)
        total = len(self.probes)
        repaired = sum(p.repaired for p in self.probes.values())
        repaired_suffix = f", {repaired} repaired" if repaired else ""

        self.passed_probes_count = passed
        self.total_probes_count = total
        self.all_passed = bool(total > 0 and passed == total)
        self.summary_label = f"{passed}/{total} passed{repaired_suffix}"


def _create_evaluator(probe_name: str) -> Any:
    """Map probe name to its deterministic evaluator."""
    if probe_name == "json_adherence":
        from devops_cli.ai.gateway_evaluators import JsonAdherenceEvaluator

        return JsonAdherenceEvaluator()
    if probe_name == "tool_choice":
        from devops_cli.ai.gateway_evaluators import ToolChoiceEvaluator

        return ToolChoiceEvaluator()
    if probe_name == "deep_recall":
        from devops_cli.ai.gateway_evaluators import DeepRecallEvaluator

        return DeepRecallEvaluator()
    from devops_cli.ai.gateway_evaluators import ExplicitProhibitionEvaluator

    return ExplicitProhibitionEvaluator()


def _evaluate_trial(rc: Any) -> tuple[bool, bool, str | None]:
    """Extract pass status, repair status, and detail from one trial report case."""
    raw_output = str(rc.output)
    fixed = fix_llm_response(raw_output)
    eval_res = next(iter(rc.assertions.values()), None)
    is_passed = bool(eval_res.value) if eval_res else False
    detail = eval_res.reason if (eval_res and not is_passed and eval_res.reason) else None
    return is_passed, fixed.was_repaired, detail


def _aggregate_probe_score(name: str, rcs: list[Any]) -> CapabilityProbeScore:
    """Aggregate multiple trial cases for a single probe into a CapabilityProbeScore."""
    trials_count = len(rcs)
    passed_count = 0
    repaired_count = 0
    details: list[str] = []

    for rc in rcs:
        passed, repaired, detail = _evaluate_trial(rc)
        if passed:
            passed_count += 1
        if repaired:
            repaired_count += 1
        if detail:
            details.append(detail)

    success_rate = (passed_count / trials_count) if trials_count > 0 else 0.0
    return CapabilityProbeScore(
        name=name,
        trials=trials_count,
        passed=passed_count,
        repaired=repaired_count,
        success_rate=round(success_rate, 4),
        details=details,
    )


def score_deployment_probes(
    probe_replies: dict[str, list[str]],
    repeat: int = 1,
) -> DeploymentCapabilities:
    """Score collected probe replies with pydantic_evals Dataset and deterministic evaluators."""
    if not probe_replies:
        return DeploymentCapabilities(probed=False)

    from pydantic_evals import Case, Dataset

    cases: list[Case[str, str, None]] = [
        Case(
            name=name,
            inputs=name,
            expected_output="valid",
            evaluators=[_create_evaluator(name)],
        )
        for name in CONST_CAPABILITY_PROBE_NAMES
        if name in probe_replies
    ]

    if not cases:
        return DeploymentCapabilities(probed=False)

    reply_iterators = {k: iter(v) for k, v in probe_replies.items()}

    def task(case_name: str) -> str:
        it = reply_iterators.get(case_name)
        if it is None:
            return ""
        return next(it, "")

    dataset = Dataset(name="capability_probes", cases=cases)
    report = dataset.evaluate_sync(task, repeat=repeat, progress=False)

    case_reports: dict[str, list[Any]] = {}
    for rc in report.cases:
        source_name = getattr(rc, "source_case_name", None) or (
            rc.name.split(" [")[0] if rc.name else ""
        )
        case_reports.setdefault(source_name, []).append(rc)

    evaluated_probes = {
        name: _aggregate_probe_score(name, rcs) for name, rcs in case_reports.items()
    }

    return DeploymentCapabilities(
        probed=True,
        trials=repeat,
        probes=evaluated_probes,
    )
