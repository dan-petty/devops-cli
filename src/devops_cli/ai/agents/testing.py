"""Pydantic AI Testing utilities, TestModel, FunctionModel, and run capture helpers."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal

from pydantic import BaseModel, Field

from devops_cli.exceptions import DevOpsCLIError
from devops_cli.models.ai import ChatMessage

ALLOW_MODEL_REQUESTS: bool = True
_RUN_MESSAGES_CAPTURE: ContextVar[list[Any] | None] = ContextVar(
    "_RUN_MESSAGES_CAPTURE", default=None
)


class ModelNotAllowedError(DevOpsCLIError):
    """Raised when a non-test model request is attempted while ALLOW_MODEL_REQUESTS is False."""

    def __init__(
        self,
        message: str = "Real model requests are disabled during testing (ALLOW_MODEL_REQUESTS=False)",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, error_code="MODEL_REQUESTS_DISABLED", **kwargs)


@contextmanager
def capture_run_messages() -> Iterator[list[Any]]:
    """Context manager that captures all message exchanges during an agent run."""
    messages: list[Any] = []
    token = _RUN_MESSAGES_CAPTURE.set(messages)
    try:
        yield messages
    finally:
        _RUN_MESSAGES_CAPTURE.reset(token)


class AgentInfo(BaseModel):
    """Metadata passed to FunctionModel callbacks."""

    agent_name: str = "Assistant"
    tools: list[str] = Field(default_factory=list)
    output_schema: Any | None = None


class TestModel(BaseModel):
    """Deterministic mock model for unit testing agent logic and tool orchestration without real LLMs."""

    __test__ = False

    model_name: str = "test"
    custom_output_text: str | None = None
    custom_output_args: dict[str, Any] | None = None
    call_tools: list[str] | Literal["all"] = "all"
    seed: int | None = None

    def chat(self, messages: list[ChatMessage | dict[str, Any]] | str, **kwargs: Any) -> str:
        """Emulate chat response."""
        if self.custom_output_text is not None:
            return self.custom_output_text
        if self.custom_output_args is not None:
            return json.dumps(self.custom_output_args)
        return '{"result": "test_success", "status": "ok"}'

    def chat_messages(
        self,
        system_or_messages: str | list[ChatMessage | dict[str, Any]],
        messages: list[ChatMessage | dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        actual_messages = messages if messages is not None else system_or_messages
        return self.chat(actual_messages, **kwargs)


class FunctionModel(BaseModel):
    """Custom programmatic model that delegates message completion to a user-supplied Python function."""

    function: Callable[..., Any]
    model_name: str = "function_model"

    def chat(self, messages: list[ChatMessage | dict[str, Any]] | str, **kwargs: Any) -> str:
        info = AgentInfo(agent_name=str(kwargs.get("agent_name", "Assistant")))
        result = self.function(messages, info)
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return json.dumps(result)
        return str(getattr(result, "content", result))

    def chat_messages(
        self,
        system_or_messages: str | list[ChatMessage | dict[str, Any]],
        messages: list[ChatMessage | dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        actual_messages = messages if messages is not None else system_or_messages
        return self.chat(actual_messages, **kwargs)
