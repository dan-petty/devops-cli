"""Deterministic capability probe evaluators scored with pydantic_evals (#595).

This module holds evaluator implementations and is loaded lazily on demand
so that CLI startup does not import pydantic_evals or heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from devops_cli.ai.response_repair import fix_llm_response
from devops_cli.config.constants import (
    CONST_CAPABILITY_PROBE_CANARY,
    CONST_CAPABILITY_PROBE_DEFAULT_TOOL,
    CONST_CAPABILITY_PROBE_FORBIDDEN_WORDS,
    CONST_CAPABILITY_PROBE_JSON_FIELDS,
    CONST_CAPABILITY_PROBE_PROHIBITION_PREFIX,
)


@dataclass
class JsonAdherenceEvaluator(Evaluator[str, str, None]):
    """Evaluate whether the model response adheres to the 5-field JSON specification."""

    required_fields: tuple[str, ...] = CONST_CAPABILITY_PROBE_JSON_FIELDS

    def evaluate_raw(self, output: str) -> bool:
        """Evaluate raw output string directly."""
        fixed = fix_llm_response(output)
        data = fixed.json_data
        if not isinstance(data, dict):
            return False
        if not all(field in data for field in self.required_fields):
            return False
        line_val = data.get("line")
        return isinstance(line_val, int) or (
            isinstance(line_val, str) and line_val.strip().isdigit()
        )

    def evaluate(self, ctx: EvaluatorContext[str, str, None]) -> EvaluationReason:
        """Evaluate context output and return result with reason."""
        passed = self.evaluate_raw(ctx.output)
        reason = "Valid 5-field JSON" if passed else "Missing or invalid JSON fields"
        return EvaluationReason(value=passed, reason=reason)


@dataclass
class ToolChoiceEvaluator(Evaluator[str, str, None]):
    """Evaluate whether the model selects the expected tool from 10 choices."""

    expected_tool: str = CONST_CAPABILITY_PROBE_DEFAULT_TOOL

    def evaluate_raw(self, output: str) -> bool:
        """Evaluate raw output string directly."""
        clean = output.strip().lower()
        return self.expected_tool.lower() in clean

    def evaluate(self, ctx: EvaluatorContext[str, str, None]) -> EvaluationReason:
        """Evaluate context output and return result with reason."""
        passed = self.evaluate_raw(ctx.output)
        reason = f"Selected {self.expected_tool}" if passed else "Wrong tool chosen"
        return EvaluationReason(value=passed, reason=reason)


@dataclass
class DeepRecallEvaluator(Evaluator[str, str, None]):
    """Evaluate whether the model recalls a canary token placed deep in context."""

    canary: str = CONST_CAPABILITY_PROBE_CANARY

    def evaluate_raw(self, output: str) -> bool:
        """Evaluate raw output string directly."""
        return self.canary.lower() in output.lower()

    def evaluate(self, ctx: EvaluatorContext[str, str, None]) -> EvaluationReason:
        """Evaluate context output and return result with reason."""
        passed = self.evaluate_raw(ctx.output)
        reason = "Canary found" if passed else "Canary not recalled"
        return EvaluationReason(value=passed, reason=reason)


@dataclass
class ExplicitProhibitionEvaluator(Evaluator[str, str, None]):
    """Evaluate instruction adherence with explicit negative constraints."""

    forbidden: tuple[str, ...] = CONST_CAPABILITY_PROBE_FORBIDDEN_WORDS
    required_prefix: str = CONST_CAPABILITY_PROBE_PROHIBITION_PREFIX

    def evaluate_raw(self, output: str) -> bool:
        """Evaluate raw output string directly."""
        stripped = output.strip()
        if not stripped:
            return False
        if not stripped.upper().startswith(self.required_prefix.upper()):
            return False
        lower = stripped.lower()
        return not any(word.lower() in lower for word in self.forbidden)

    def evaluate(self, ctx: EvaluatorContext[str, str, None]) -> EvaluationReason:
        """Evaluate context output and return result with reason."""
        passed = self.evaluate_raw(ctx.output)
        reason = "Complied with prohibition" if passed else "Violated prohibition"
        return EvaluationReason(value=passed, reason=reason)
