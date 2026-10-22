"""The request for ASD-STE100 Simplified Technical English that every free-text model call carries."""

from __future__ import annotations

from devops_cli.ai.task_loader import load_task_prompt


def with_style_request(system: str) -> str:
    """The system prompt, then the style request from `style_ste100.md`.

    The request follows the caller's prompt and never replaces it. A prompt that already holds
    the request comes back as it is. A structured call puts the request ahead of its schema, so
    the chat call that it makes does not add the request again. The request tells the model to
    keep any output format that the task sets, so code, data and structured replies keep theirs.
    """
    request = load_task_prompt("style_ste100.md")
    if request in system:
        return system
    return f"{system}\n\n{request}" if system.strip() else request
