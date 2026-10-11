"""Client protocol for models driving review and verification."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReviewLLMClient(Protocol):
    """Client protocol for models driving review and verification."""

    @property
    def backend_info(self) -> str: ...

    def chat(
        self,
        system: str,
        user: str,
        **kwargs: Any,
    ) -> Any: ...

    def chat_messages(
        self,
        system: str = "",
        messages: Any = None,
        **kwargs: Any,
    ) -> Any: ...

    def get_context_window(self, task: str | None = None) -> int: ...
