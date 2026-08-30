"""Pydantic AI Guardrails validation layers for inputs, tool calls, and model outputs."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.capabilities import BaseCapability
from devops_cli.ai.agents.context import AgentHooks, RunContext


class GuardrailAction(StrEnum):
    """Guardrail disposition action."""

    ALLOW = "allow"
    BLOCK = "block"
    REPLACE = "replace"
    RETRY = "retry"


class GuardrailResult(BaseModel):
    """Structured result returned by an input, tool, or output guardrail callable."""

    action: GuardrailAction = GuardrailAction.ALLOW
    content: Any = None
    message: str = ""

    @classmethod
    def allow(cls, content: Any = None) -> GuardrailResult:
        """Allow the payload through as-is or with optional content."""
        return cls(action=GuardrailAction.ALLOW, content=content)

    @classmethod
    def block(cls, message: str = "Blocked by safety guardrail") -> GuardrailResult:
        """Block execution and return a refusal or safety violation message."""
        return cls(action=GuardrailAction.BLOCK, message=message)

    @classmethod
    def replace(cls, content: Any, message: str = "") -> GuardrailResult:
        """Replace the input, tool args, or output with a sanitized or transformed substitute."""
        return cls(action=GuardrailAction.REPLACE, content=content, message=message)

    @classmethod
    def retry(
        cls, message: str = "Validation failed. Please correct and retry."
    ) -> GuardrailResult:
        """Request that the model retry generation with corrective feedback."""
        return cls(action=GuardrailAction.RETRY, message=message)


InputGuardrailFn = Callable[[RunContext[Any], str], GuardrailResult | str | None]
ToolGuardrailFn = Callable[
    [RunContext[Any], str, dict[str, Any]], GuardrailResult | dict[str, Any] | None
]
OutputGuardrailFn = Callable[[RunContext[Any], Any], GuardrailResult | Any | None]


class InputGuardrail(BaseModel):
    """Inspects and optionally modifies or blocks user prompts before dispatch to LLM."""

    name: str = "input_guardrail"
    handler: Any = None

    def execute(self, ctx: RunContext[Any], prompt: str) -> GuardrailResult:
        """Execute the input guardrail check."""
        if not callable(self.handler):
            return GuardrailResult.allow()
        res = self.handler(ctx, prompt)
        if isinstance(res, GuardrailResult):
            return res
        elif isinstance(res, str):
            return GuardrailResult.replace(res) if res != prompt else GuardrailResult.allow()
        return GuardrailResult.allow()


class ToolGuardrail(BaseModel):
    """Inspects and validates tool invocation arguments and execution permissions."""

    name: str = "tool_guardrail"
    handler: Any = None

    def execute(
        self, ctx: RunContext[Any], tool_name: str, args: dict[str, Any]
    ) -> GuardrailResult:
        """Execute the tool invocation guardrail check."""
        if not callable(self.handler):
            return GuardrailResult.allow()
        res = self.handler(ctx, tool_name, args)
        if isinstance(res, GuardrailResult):
            return res
        elif isinstance(res, dict):
            return GuardrailResult.replace(res)
        return GuardrailResult.allow()


class OutputGuardrail(BaseModel):
    """Inspects, sanitizes, or retries the final model response before returning."""

    name: str = "output_guardrail"
    handler: Any = None

    def execute(self, ctx: RunContext[Any], output: Any) -> GuardrailResult:
        """Execute the output guardrail check."""
        if not callable(self.handler):
            return GuardrailResult.allow()
        res = self.handler(ctx, output)
        if isinstance(res, GuardrailResult):
            return res
        elif res is not None and res != output:
            return GuardrailResult.replace(res)
        return GuardrailResult.allow()


class GuardrailCapability(BaseCapability):
    """Capability bundling input, tool, and output guardrail layers."""

    id: str = "guardrails"
    input_guardrails: list[InputGuardrail] = Field(default_factory=list)
    tool_guardrails: list[ToolGuardrail] = Field(default_factory=list)
    output_guardrails: list[OutputGuardrail] = Field(default_factory=list)

    def add_input_guardrail(
        self, fn: InputGuardrailFn, *, name: str = "input_guardrail"
    ) -> GuardrailCapability:
        """Register an input prompt guardrail."""
        self.input_guardrails.append(InputGuardrail(name=name, handler=fn))
        return self

    def add_tool_guardrail(
        self, fn: ToolGuardrailFn, *, name: str = "tool_guardrail"
    ) -> GuardrailCapability:
        """Register a tool invocation guardrail."""
        self.tool_guardrails.append(ToolGuardrail(name=name, handler=fn))
        return self

    def add_output_guardrail(
        self, fn: OutputGuardrailFn, *, name: str = "output_guardrail"
    ) -> GuardrailCapability:
        """Register a model output guardrail."""
        self.output_guardrails.append(OutputGuardrail(name=name, handler=fn))
        return self

    def get_hooks(self) -> AgentHooks | None:
        """Bind guardrail execution into agent lifecycle hooks."""

        def before_tool(ctx: RunContext[Any], tool_name: str, args: dict[str, Any]) -> None:
            for tg in self.tool_guardrails:
                res = tg.execute(ctx, tool_name, args)
                if res.action == GuardrailAction.BLOCK:
                    raise PermissionError(
                        res.message or f"Tool call {tool_name} blocked by safety guardrail."
                    )
                elif res.action == GuardrailAction.REPLACE and isinstance(res.content, dict):
                    args.clear()
                    args.update(res.content)

        return AgentHooks(before_tool_execute=[before_tool])

    def run_input_guardrails(self, ctx: RunContext[Any], prompt: str) -> str:
        """Execute all registered input guardrails sequentially."""
        current_prompt = prompt
        for ig in self.input_guardrails:
            res = ig.execute(ctx, current_prompt)
            if res.action == GuardrailAction.BLOCK:
                raise PermissionError(res.message or "Input prompt blocked by safety guardrail.")
            elif res.action == GuardrailAction.REPLACE and isinstance(res.content, str):
                current_prompt = res.content
        return current_prompt

    def run_output_guardrails(self, ctx: RunContext[Any], output: Any) -> Any:
        """Execute all registered output guardrails sequentially."""
        current_output = output
        for og in self.output_guardrails:
            res = og.execute(ctx, current_output)
            if res.action == GuardrailAction.BLOCK:
                raise PermissionError(res.message or "Output blocked by safety guardrail.")
            elif res.action == GuardrailAction.REPLACE and res.content is not None:
                current_output = res.content
        return current_output
