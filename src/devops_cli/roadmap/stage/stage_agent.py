"""The stage agent on stock `Coder` (#6705).

The agent is one pydantic-ai `Agent` on the model of the task `stage`:

- `LocalWorkspace` at the clone of `prepare`. Its commands get a scratch `HOME`, the configuration
  file of the process (`DEVOPS_CLI_CONFIG`), so that the checks of the agent read the settings
  that `publish` reads, `GIT_CONFIG_NOSYSTEM=1` and `GIT_TERMINAL_PROMPT=0`. `LocalWorkspace`
  passes only `PATH`, `HOME`, `LANG`, `LC_ALL` and `LC_CTYPE` of the process to a command.
- `Coder` with no repository context and no `delegate_task`, with its stock shell (a wait of
  `MAX_FOREGROUND_WAIT` for a command) and its context controls on the window of the task.
- `RequireVerification` with no exempt path, so an edit of a plan file counts, and the patterns of
  the three checks in order: `devops openspec check`, `openspec validate <change> --strict`, and
  `devops roadmap plan-recheck` with `--branch HEAD`, `--base <sha>` and `--candidate <file>`. It
  sends a run back to its checks; `publish` runs the checks again as the gate.
- `Hooks` with a listener of `CompletionUnverifiedEvent` and a check of the time budget before
  each model request.

The agent has no tool of its own. The shell is no security boundary: the agent phase holds no
GitHub credential.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import AbstractCapability, Hooks, LocalWorkspace
from pydantic_ai.models import ModelRequestContext
from pydantic_ai_harness.coder import Coder
from pydantic_ai_harness.compaction import ClearToolResults, WarnNearLimits
from pydantic_ai_harness.require_verification import (
    CompletionUnverifiedEvent,
    RequireVerification,
)

from devops_cli.exceptions import RoadmapTimeBudgetError
from devops_cli.lang import MESSAGES

# A command may start with `uv run`, as a person runs it.
_UV: Final[str] = r"(?:uv\s+run(?:\s+-\S+)*\s+)?"
# The three checks of the stage agent, in order, as `RequireVerification` matches them at the
# start of a step of a command.
STAGE_CHECKS: Final[tuple[str, ...]] = (
    rf"{_UV}devops\s+openspec\s+check\b",
    r"(?:npx\s+)?openspec\s+validate\b(?=[^\n]*\s--strict\b)",
    rf"{_UV}devops\s+roadmap\s+plan-recheck\b"
    r"(?=[^\n]*\s--branch\s+HEAD\b)"
    r"(?=[^\n]*\s--base\s+[0-9a-f]{7,40}\b)"
    r"(?=[^\n]*\s--candidate\s+\S)",
)


@dataclass
class StageRunLog:
    """What the hooks of the stage agent saw: the event of a run that ended unverified."""

    unverified: CompletionUnverifiedEvent | None = None
    failed_checks: list[str] = field(default_factory=list)


def workspace_env(home: Path, config: Path | None) -> dict[str, str]:
    """The environment of each command of the agent, on top of what `LocalWorkspace` passes."""
    env = {"HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
    if config is not None:
        env["DEVOPS_CLI_CONFIG"] = str(config)
    return env


def _windowed(window: int) -> Any:
    """The visitor that gives the context controls of `Coder` the window of the task."""

    def visit(leaf: AbstractCapability[None]) -> AbstractCapability[None]:
        if isinstance(leaf, ClearToolResults | WarnNearLimits):
            return replace(leaf, context_window=window)
        return leaf

    return visit


def _hooks(log: StageRunLog, deadline: datetime) -> Hooks[None]:
    """The listener of the unverified end and the check of the time budget."""
    hooks = Hooks[None]()

    @hooks.on.event(CompletionUnverifiedEvent)
    async def unverified(_ctx: RunContext[None], event: CompletionUnverifiedEvent) -> None:
        log.unverified = event
        log.failed_checks = list(event.failed_commands)

    @hooks.on.before_model_request
    async def within_budget(
        _ctx: RunContext[None], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        if datetime.now(UTC) >= deadline:
            raise RoadmapTimeBudgetError(
                MESSAGES.roadmap.stage_agent_budget_spent.format(deadline=deadline.isoformat())
            )
        return request_context

    return hooks


def build_stage_agent(
    model: Any,
    clone: Path,
    *,
    home: Path,
    config: Path | None,
    instructions: str,
    window: int,
    deadline: datetime,
    log: StageRunLog,
) -> Agent[None, str]:
    """The stage agent, as the module says, in the clone `clone`. `home` is the scratch home of
    its commands, `config` the configuration file of the process, `instructions` the prompt of the
    task, `window` the context window of the task, `deadline` the end time of the time budget, and
    `log` what the hooks record."""
    coder = Coder[None](instructions=instructions, repo_context=False, sub_agents=False)
    tuned = cast("AbstractCapability[None]", coder.visit_and_replace(_windowed(window)))
    return Agent(
        model,
        output_type=str,
        capabilities=[
            LocalWorkspace(clone, env=workspace_env(home, config)),
            tuned,
            RequireVerification[None](
                instructions=MESSAGES.roadmap.stage_agent_verify,
                verification_commands=STAGE_CHECKS,
                exempt_paths=(),
            ),
            _hooks(log, deadline),
        ],
    )


__all__ = ["STAGE_CHECKS", "StageRunLog", "build_stage_agent", "workspace_env"]
