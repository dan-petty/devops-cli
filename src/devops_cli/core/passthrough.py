"""Declarative registry for CLI commands that mirror and forward underlying tool options."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Literal

from devops_cli.config.defaults import DEFAULT_GH_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.github.rate_limiter import run_gh

ToolMode = Literal["read", "write"]
PassthroughRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class OwnedOption:
    """One tool option that the devops wrapper parses, validates, or exposes."""

    flags: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class McpOptionRule:
    """Arity and value/length bounds enforced for one MCP-exposed tool option."""

    arity: int
    max_value: int | None = None
    max_length: int | None = None
    description: str = ""

    @property
    def cap(self) -> int | None:
        """Numeric ceiling or string-length cap for this option."""
        return self.max_value if self.max_value is not None else self.max_length


@dataclass(frozen=True)
class PageRule:
    """Paging and rate-limit cost rule mapped to a list command's limit flag."""

    flags: tuple[str, ...]
    default_limit: int
    max_limit: int
    items_per_unit: int


@dataclass(frozen=True)
class PassthroughEntry:
    """Registry contract describing one pass-through CLI command."""

    devops_paths: tuple[str, ...]
    runner: PassthroughRunner
    mode: ToolMode
    owned_options: Mapping[str, OwnedOption]
    refused_options: Mapping[str, str]
    mcp_allowlist: Mapping[str, McpOptionRule]
    run_cost: int
    page_rule: PageRule
    timeout: float


# Verbs of `gh` that devops-cli never wraps or exposes through pass-through commands.
NEVER_WRAPPED: Final[frozenset[str]] = frozenset(
    {
        "pr merge",
        "auth",
        "secret set",
        "repo delete",
        "release",
    }
)

_GH_RUN_LIST_OWNED: Final[dict[str, OwnedOption]] = {
    "--repo": OwnedOption(
        flags=("-R", "--repo"),
        description="Target GitHub repository in OWNER/REPO format.",
    ),
    "--limit": OwnedOption(
        flags=("-L", "--limit"),
        description="Maximum number of workflow runs to fetch.",
    ),
    "--branch": OwnedOption(
        flags=("-b", "--branch"),
        description="Filter workflow runs by branch name.",
    ),
    "--workflow": OwnedOption(
        flags=("-w", "--workflow"),
        description="Filter workflow runs by workflow file or name.",
    ),
    "--status": OwnedOption(
        flags=("-s", "--status"),
        description="Filter workflow runs by execution status.",
    ),
    "--json": OwnedOption(
        flags=("--json",),
        description="Output JSON with selected gh workflow run fields.",
    ),
    "--jq": OwnedOption(
        flags=("-q", "--jq"),
        description="Filter JSON output using a jq expression.",
    ),
}

_GH_RUN_LIST_MCP_ALLOWLIST: Final[dict[str, McpOptionRule]] = {
    "--repo": McpOptionRule(arity=1, max_length=200, description="Validated OWNER/REPO."),
    "--limit": McpOptionRule(arity=1, max_value=100, description="Max workflow runs returned."),
    "--branch": McpOptionRule(arity=1, max_length=200, description="Git branch filter."),
    "--workflow": McpOptionRule(arity=1, max_length=200, description="Workflow identifier filter."),
    "--status": McpOptionRule(arity=1, max_length=64, description="Workflow run status filter."),
    "--json": McpOptionRule(arity=1, max_length=512, description="Comma-separated JSON fields."),
    "--jq": McpOptionRule(arity=1, max_length=512, description="jq filter expression."),
}

REGISTRY: Final[dict[str, PassthroughEntry]] = {
    "gh run list": PassthroughEntry(
        devops_paths=("devops gh run list",),
        runner=run_gh,
        mode="read",
        owned_options=_GH_RUN_LIST_OWNED,
        refused_options={
            "--hostname": "Custom GitHub Enterprise hosts are refused to prevent unintended egress.",
            "--web": "Interactive browser launches are refused in automated and wrapper execution.",
        },
        mcp_allowlist=_GH_RUN_LIST_MCP_ALLOWLIST,
        run_cost=1,
        page_rule=PageRule(
            flags=("-L", "--limit"),
            default_limit=20,
            max_limit=100,
            items_per_unit=100,
        ),
        timeout=DEFAULT_GH_SUBPROCESS_TIMEOUT_SECONDS,
    ),
}


def get_passthrough_entry(tool_path: str) -> PassthroughEntry:
    """Return the registered entry for `tool_path`."""
    return REGISTRY[tool_path]


__all__ = [
    "NEVER_WRAPPED",
    "REGISTRY",
    "McpOptionRule",
    "OwnedOption",
    "PageRule",
    "PassthroughEntry",
    "PassthroughRunner",
    "ToolMode",
    "get_passthrough_entry",
]
