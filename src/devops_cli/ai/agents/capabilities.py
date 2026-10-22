"""Agent capability base class, deferred tool call handling, and periodic system reminders."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import (
    ToolCallPart as ToolCallPart,
)

from devops_cli.ai.agents.context import AgentHooks, RunContext
from devops_cli.ai.agents.tools import AgentTool
from devops_cli.ai.tools import (
    DeferredToolRequests as DeferredToolRequests,
)
from devops_cli.ai.tools import (
    DeferredToolResults as DeferredToolResults,
)
from devops_cli.ai.tools import (
    ToolApproved as ToolApproved,
)
from devops_cli.ai.tools import (
    ToolDenied as ToolDenied,
)
from devops_cli.config.defaults import (
    DEFAULT_PLAN_REMINDER_CADENCE,
    DEFAULT_PLAN_REMINDER_ID,
)


class BaseCapability(BaseModel, AbstractCapability[Any]):
    """Abstract base class for modular agent capabilities."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    id: str | None = ""
    description: str | None = ""
    defer_loading: bool = False

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        """Return tools provided by this capability."""
        return []

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        """Return prompt additions provided by this capability."""
        return []

    def get_hooks(self) -> AgentHooks | None:
        """Return lifecycle hooks provided by this capability."""
        return None

    def get_model_settings(  # type: ignore[override]
        self, ctx: RunContext[Any] | None = None
    ) -> dict[str, Any]:
        """Return model runtime settings provided by this capability."""
        return {}

    # ── Pydantic AI AbstractCapability Protocol Implementation ─────────────────

    def get_instructions(self) -> list[str] | None:
        """Return instructions to include in the system prompt for native Pydantic AI agents."""
        additions = self.get_system_prompt_additions()
        if additions:
            return additions
        if hasattr(self, "instructions") and getattr(self, "instructions"):
            return [str(getattr(self, "instructions"))]
        return None

    def get_toolset(self) -> Any:
        """Return native FunctionToolset wrapping tools for native Pydantic AI agents."""
        tools = self.get_tools()
        if not tools:
            return None
        try:
            from devops_cli.ai.toolsets import create_function_toolset

            return create_function_toolset(tools=tools)
        except Exception:
            return None

    def get_native_tools(self) -> list[Any]:
        """Return native provider tools registered with this capability."""
        return []

    def get_description(self) -> str | None:
        """Return a human-readable description of this capability."""
        return self.description or None

    async def before_run(self, ctx: Any) -> None:
        """Lifecycle hook invoked before an agent run starts."""
        hooks = self.get_hooks()
        if hooks:
            for hook in hooks.before_run:
                hook(ctx)

    async def after_run(self, ctx: Any, *, result: Any) -> Any:
        """Lifecycle hook invoked after an agent run completes."""
        hooks = self.get_hooks()
        if hooks:
            for hook in hooks.after_run:
                hook(ctx, result)
        return result

    async def before_tool_execute(
        self,
        ctx: Any,
        *,
        call: Any = None,
        tool_def: Any = None,
        args: Any = None,
    ) -> Any:
        """Lifecycle hook invoked before executing a tool."""
        hooks = self.get_hooks()
        if hooks:
            tool_name = getattr(call, "tool_name", getattr(tool_def, "name", str(tool_def)))
            for hook in hooks.before_tool_execute:
                hook(ctx, tool_name, args)
        return args

    async def after_tool_execute(
        self,
        ctx: Any,
        *,
        call: Any = None,
        tool_def: Any = None,
        args: Any = None,
        result: Any = None,
    ) -> Any:
        """Lifecycle hook invoked after executing a tool."""
        hooks = self.get_hooks()
        if hooks:
            tool_name = getattr(call, "tool_name", getattr(tool_def, "name", str(tool_def)))
            for hook in hooks.after_tool_execute:
                hook(ctx, tool_name, result)
        return result


def _accepts_positional_arguments(func: Callable[..., Any], count: int) -> bool:
    """Whether ``func`` can be called with ``count`` positional arguments and nothing else.

    ``**kwargs`` and keyword-only parameters take no positional argument, so
    ``handler(requests, **kw)`` accepts one and not two.
    """
    try:
        inspect.signature(func).bind(*[None] * count)
    except TypeError:
        return False
    return True


class HandleDeferredToolCalls(BaseCapability):
    """Capability providing inline handling of deferred tool calls and approvals."""

    id: str | None = "handle_deferred_tool_calls"
    handler: Any = None

    def __init__(
        self,
        handler: Callable[..., DeferredToolResults | None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(handler=handler or kwargs.get("handler"), **kwargs)

    def handle_deferred(
        self, requests: DeferredToolRequests, ctx: RunContext[Any] | None = None
    ) -> DeferredToolResults | None:
        """Execute the deferred tool call handler callback.

        The call is chosen by the handler's signature alone. A handler that can be called with
        the requests alone, such as ``(requests)`` or ``(requests, **kwargs)``, gets them alone.
        Any other gets ``(ctx, requests)``, as pydantic-ai calls it, with a fresh ``RunContext``
        when none is given.
        """
        if not callable(self.handler):
            return None
        res: Any = (
            self.handler(requests)
            if _accepts_positional_arguments(self.handler, 1)
            else self.handler(ctx if ctx is not None else RunContext(), requests)
        )
        if isinstance(res, DeferredToolResults):
            return res
        return None


class SystemReminders(BaseCapability):
    """Capability that combats instruction fade by re-injecting targeted behavioral guidance on a cadence."""

    id: str | None = DEFAULT_PLAN_REMINDER_ID
    reminders: list[str] = Field(default_factory=list)
    cadence: int = DEFAULT_PLAN_REMINDER_CADENCE
    condition: Any = None
    _turn_counter: int = 0

    def __init__(
        self,
        reminders: list[str] | None = None,
        *,
        cadence: int = DEFAULT_PLAN_REMINDER_CADENCE,
        condition: Callable[[RunContext[Any], int], bool] | None = None,
        id: str = DEFAULT_PLAN_REMINDER_ID,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            id=id,
            reminders=reminders or [],
            cadence=cadence,
            condition=condition,
            **kwargs,
        )

    def should_remind(self, ctx: RunContext[Any], turn: int) -> bool:
        """Determine whether reminders should be injected on the current turn."""
        if callable(self.condition):
            return bool(self.condition(ctx, turn))
        return self.cadence > 0 and (turn % self.cadence == 0)

    def get_reminders(self, ctx: RunContext[Any], turn: int) -> list[str]:
        """Return reminders to inject if the cadence or condition is satisfied."""
        if self.should_remind(ctx, turn):
            return list(self.reminders)
        return []

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if ctx is not None:
            self._turn_counter += 1
            return self.get_reminders(ctx, self._turn_counter)
        return list(self.reminders)
