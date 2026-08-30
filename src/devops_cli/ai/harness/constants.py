"""Constants and deprecation warnings for Pydantic AI Harness."""

from __future__ import annotations

import logging

from devops_cli.ai.task_loader import load_task_prompt

logger = logging.getLogger(__name__)

DEFAULT_ADVISOR_INSTRUCTIONS: str = load_task_prompt("advisor_system.md").strip()
DEFAULT_SUMMARIZING_INSTRUCTIONS: str = load_task_prompt("summarizing_compaction.md").strip()
DEFAULT_CODER_INSTRUCTIONS: str = load_task_prompt("coder_agent.md").strip()
DEFAULT_RESEARCHER_INSTRUCTIONS: str = load_task_prompt("researcher_agent.md").strip()
DEFAULT_MACROSCOPE_GUIDANCE: str = load_task_prompt("macroscope_guidance.md").strip()
DEFAULT_PLANNING_GUIDANCE: str = (
    load_task_prompt("planning_guidance.md").strip()
    or "Use the planning tools (write_plan, read_plan, update_task_status) to track progress across multi-step tasks."
)
DEFAULT_PLAYWRIGHT_GUIDANCE: str = (
    load_task_prompt("playwright_guidance.md").strip()
    or "Use browser automation tools (navigate, snapshot, click, type_text) to interact with web applications."
)

LLM_API_KEY_ENV_PATTERNS: list[str] = [
    "*API_KEY*",
    "*AUTH_TOKEN*",
    "*SECRET*",
    "*PASSWORD*",
    "*ACCESS_TOKEN*",
    "*CREDENTIAL*",
]

DEFAULT_PROTECTED_PATTERNS: list[str] = [
    ".git/*",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "**/secrets*",
]

DEFAULT_DENIED_COMMANDS: set[str] = {
    "rm",
    "rmdir",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "poweroff",
    "init",
}

INTERACTIVE_COMMANDS: set[str] = {
    "vim",
    "vi",
    "nano",
    "top",
    "htop",
    "less",
    "more",
}

UNSUPPORTED_BEHAVIORAL_SKILL_FIELDS: set[str] = {
    "agent",
    "allowed-tools",
    "argument-hint",
    "arguments",
    "context",
    "dependencies",
    "disable-model-invocation",
    "disallowed-tools",
    "effort",
    "hooks",
    "model",
    "paths",
    "shell",
    "tools",
    "user-invocable",
    "when_to_use",
}


class HarnessDeprecationWarning(DeprecationWarning):
    """Warning category raised for deprecated Pydantic AI Harness options or defaults."""
