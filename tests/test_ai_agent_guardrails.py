"""Unit tests for Pydantic AI Guardrails validation layers and capabilities."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.agents import (
    GuardrailAction,
    GuardrailCapability,
    GuardrailResult,
    InputGuardrail,
    OutputGuardrail,
    RunContext,
    ToolGuardrail,
)


def test_guardrail_result_constructors() -> None:
    """Verify classmethod constructors on GuardrailResult."""
    allow = GuardrailResult.allow("content1")
    assert allow.action == GuardrailAction.ALLOW
    assert allow.content == "content1"

    block = GuardrailResult.block("Blocked by safety policy")
    assert block.action == GuardrailAction.BLOCK
    assert "safety policy" in block.message

    replace = GuardrailResult.replace("sanitized", "Redacted PII")
    assert replace.action == GuardrailAction.REPLACE
    assert replace.content == "sanitized"
    assert replace.message == "Redacted PII"

    retry = GuardrailResult.retry("Please format as JSON")
    assert retry.action == GuardrailAction.RETRY
    assert "format as JSON" in retry.message


def test_input_guardrail_execution() -> None:
    """Verify InputGuardrail execution patterns."""
    ctx = RunContext()

    # 1. Passthrough without handler
    ig_empty = InputGuardrail()
    assert ig_empty.execute(ctx, "hello").action == GuardrailAction.ALLOW

    # 2. Handler returning GuardrailResult
    def block_handler(c: RunContext[Any], prompt: str) -> GuardrailResult:
        if "malicious" in prompt:
            return GuardrailResult.block("Rejected malicious prompt")
        return GuardrailResult.allow()

    ig_block = InputGuardrail(name="blocker", handler=block_handler)
    assert ig_block.execute(ctx, "safe prompt").action == GuardrailAction.ALLOW
    assert ig_block.execute(ctx, "malicious prompt").action == GuardrailAction.BLOCK

    # 3. Handler returning modified string
    def redact_handler(c: RunContext[Any], prompt: str) -> str:
        return prompt.replace("secret_token_123", "[REDACTED]")

    ig_redact = InputGuardrail(name="redactor", handler=redact_handler)
    res = ig_redact.execute(ctx, "Use secret_token_123 here")
    assert res.action == GuardrailAction.REPLACE
    assert res.content == "Use [REDACTED] here"


def test_tool_guardrail_execution() -> None:
    """Verify ToolGuardrail execution patterns."""
    ctx = RunContext()

    # 1. Passthrough without handler
    tg_empty = ToolGuardrail()
    assert tg_empty.execute(ctx, "bash", {"cmd": "ls"}).action == GuardrailAction.ALLOW

    # 2. Block dangerous tools
    def safety_check(c: RunContext[Any], tool_name: str, args: dict[str, Any]) -> GuardrailResult:
        if tool_name == "shell" and "rm -rf" in args.get("command", ""):
            return GuardrailResult.block("Dangerous command blocked")
        return GuardrailResult.allow()

    tg_safe = ToolGuardrail(handler=safety_check)
    assert tg_safe.execute(ctx, "shell", {"command": "echo hi"}).action == GuardrailAction.ALLOW
    assert tg_safe.execute(ctx, "shell", {"command": "rm -rf /"}).action == GuardrailAction.BLOCK

    # 3. Argument transformation
    def sanitize_args(c: RunContext[Any], tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {k: v.strip() if isinstance(v, str) else v for k, v in args.items()}

    tg_transform = ToolGuardrail(handler=sanitize_args)
    res = tg_transform.execute(ctx, "test_tool", {"arg1": "  untrimmed  "})
    assert res.action == GuardrailAction.REPLACE
    assert res.content == {"arg1": "untrimmed"}


def test_output_guardrail_execution() -> None:
    """Verify OutputGuardrail execution patterns."""
    ctx = RunContext()

    # 1. Passthrough without handler
    og_empty = OutputGuardrail()
    assert og_empty.execute(ctx, "hello").action == GuardrailAction.ALLOW

    # 2. Output blocker
    def leak_detector(c: RunContext[Any], output: Any) -> GuardrailResult:
        if "PRIVATE_KEY" in str(output):
            return GuardrailResult.block("Private key detected in output")
        return GuardrailResult.allow()

    og_leak = OutputGuardrail(handler=leak_detector)
    assert og_leak.execute(ctx, "Normal text").action == GuardrailAction.ALLOW
    assert og_leak.execute(ctx, "PRIVATE_KEY=xyz").action == GuardrailAction.BLOCK


def test_guardrail_capability_workflow() -> None:
    """Verify GuardrailCapability lifecycle hooks and pipeline runners."""
    cap = GuardrailCapability()

    # 1. Add input guardrail
    cap.add_input_guardrail(lambda ctx, prompt: prompt.strip())

    ctx = RunContext()
    cleaned = cap.run_input_guardrails(ctx, "   padded prompt   ")
    assert cleaned == "padded prompt"

    # 2. Add blocking input guardrail
    cap.add_input_guardrail(
        lambda ctx, prompt: (
            GuardrailResult.block("Stop") if "forbidden" in prompt else GuardrailResult.allow()
        )
    )
    with pytest.raises(PermissionError, match="Stop"):
        cap.run_input_guardrails(ctx, "forbidden prompt")

    # 3. Tool guardrail hook binding
    cap.add_tool_guardrail(
        lambda ctx, name, args: (
            GuardrailResult.block("Tool blocked")
            if name == "unsafe_tool"
            else GuardrailResult.allow()
        )
    )
    hooks = cap.get_hooks()
    assert hooks is not None
    assert len(hooks.before_tool_execute) > 0
    hook_fn = hooks.before_tool_execute[0]

    # Safe tool passes
    hook_fn(ctx, "safe_tool", {"a": 1})

    # Blocked tool raises PermissionError
    with pytest.raises(PermissionError, match="Tool blocked"):
        hook_fn(ctx, "unsafe_tool", {"a": 1})

    # Tool argument rewriting
    cap_rewrite = GuardrailCapability()
    cap_rewrite.add_tool_guardrail(lambda ctx, name, args: {"rewritten": True})
    rewrite_hooks = cap_rewrite.get_hooks()
    assert rewrite_hooks is not None and len(rewrite_hooks.before_tool_execute) > 0
    args_dict = {"original": True}
    rewrite_hooks.before_tool_execute[0](ctx, "any_tool", args_dict)
    assert args_dict == {"rewritten": True}

    # 4. Output guardrail execution
    cap_out = GuardrailCapability()
    cap_out.add_output_guardrail(lambda ctx, out: str(out).upper())
    res_out = cap_out.run_output_guardrails(ctx, "hello world")
    assert res_out == "HELLO WORLD"

    cap_out_block = GuardrailCapability()
    cap_out_block.add_output_guardrail(lambda ctx, out: GuardrailResult.block("Output denied"))
    with pytest.raises(PermissionError, match="Output denied"):
        cap_out_block.run_output_guardrails(ctx, "data")
