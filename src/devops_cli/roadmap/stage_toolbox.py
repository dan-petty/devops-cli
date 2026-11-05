"""The planner client that calls the read-only tools (#3037).

`ToolboxClient` implements `StageClient`, so the planner, the gates and the golden-set run keep
their code. A call for a `StageProposal` is one agent run with the tools of `StageTools`: the nine of
the toolset `base`, and with `extended`, the setting `roadmap.stage.toolset`, three more (#3238). A
call for another schema goes to the inner client, with no tool. Each run has a new budget of tool
calls and requests, ends its tools when the messages fill the context window (#3037), and keeps a
`RunTrace` of what it did. It sends the counts of the run as metrics (`tool_metrics`, #3240). The
output tokens have no count of their own (#3206). A run that ends
with no plan raises `RoadmapStageError` and names the limit it hit, or
`StructuredOutputValidationError` when the model broke the schema of its reply past its retries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_MAX_REQUESTS,
    CONST_ROADMAP_STAGE_TOOL_MAX_CALLS,
)
from devops_cli.config.defaults import StageToolset
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.agent_run import RunTrace
from devops_cli.roadmap.refine_investigation import InvestigationStopped, investigate
from devops_cli.roadmap.stage_change import StageProposal
from devops_cli.roadmap.stage_github import StageGitHub
from devops_cli.roadmap.stage_tools import StageTools
from devops_cli.roadmap.tool_metrics import end_run, start_run

if TYPE_CHECKING:
    from devops_cli.roadmap.stage import StageClient

_TOOLS_TASK = "roadmap_stage_tools.md"
_EXTENDED_TOOLS_TASK = "roadmap_stage_tools_extended.md"
# The job row of the metrics of the tool calls (`row` label, #3240).
_ROW = "stage"


@dataclass(frozen=True)
class ToolboxModel:
    """The pydantic-ai model of a plan run that has the tools. Give it where the job takes a model
    to ask for a plan with the toolbox; a client instead plans with the one call and no tool."""

    model: Any


class ToolboxClient:
    """A stage client whose plan runs read the repository at `sha` with read-only tools.

    `model` is the pydantic-ai model of the run, and `inner` answers every call that is not for a
    plan. `traces` holds one `RunTrace` for each plan run, in order; the caller clears it. With a
    `window`, the context window of the model in tokens, a request that would leave too little of
    it for the plan offers no tool. `openspec` reads the specs for `read_spec`. `toolset` is
    `base` or `extended`; without it the setting `roadmap.stage.toolset` decides. `github` serves
    `read_issue` and `find_issues` of `extended`; the Service passes it, and a run without it
    answers that GitHub is not available.

    Raises `RoadmapStageError` when the checkout is not the commit `sha` with no change, because
    three tools read its files and the others read the commit.
    """

    def __init__(
        self,
        model: Any,
        inner: StageClient,
        source: Path,
        sha: str,
        *,
        window: int | None = None,
        openspec: OpenSpecTool | None = None,
        toolset: StageToolset | None = None,
        github: StageGitHub | None = None,
    ) -> None:
        self._model = model
        self._inner = inner
        chosen = toolset or load_settings().roadmap.stage.toolset
        self._tools = StageTools(
            source=source, sha=sha, openspec=openspec, toolset=chosen, github=github
        )
        self._instructions = load_task_prompt(_TOOLS_TASK)
        if chosen == "extended":
            self._instructions += f"\n\n{load_task_prompt(_EXTENDED_TOOLS_TASK)}"
        self._window = window
        self._toolset = chosen
        self._tool_names = tuple(tool.name for tool in self._tools.tools())
        self.traces: list[RunTrace] = []
        problem = self._tools.checkout_problem()
        if problem is not None:
            raise RoadmapStageError(problem)

    @property
    def reads_specs(self) -> bool:
        """Whether `read_spec` can read the specs: the run has OpenSpec."""
        return self._tools.openspec is not None

    def chat_structured[M: BaseModel](
        self, system: str, prompt: str, schema: type[M], *, max_retries: int
    ) -> M:
        """The reply of one plan run for `StageProposal`, or the inner client's reply for any
        other schema."""
        if schema is not StageProposal:
            return self._inner.chat_structured(system, prompt, schema, max_retries=max_retries)
        trace = RunTrace()
        self.traces.append(trace)
        start_run(self._tool_names, row=_ROW, toolset=self._toolset)
        finished = False
        try:
            result = investigate(
                self._model,
                f"{system}\n\n{self._instructions}",
                prompt,
                self._tools,
                schema,
                limits=UsageLimits(
                    request_limit=CONST_ROADMAP_STAGE_MAX_REQUESTS,
                    tool_calls_limit=CONST_ROADMAP_STAGE_TOOL_MAX_CALLS,
                ),
                output_retries=max_retries,
                trace=trace,
                window=self._window,
            )
            finished = True
        finally:
            end_run(trace, row=_ROW, toolset=self._toolset, finished=finished)
        if isinstance(result, InvestigationStopped):
            raise _stopped(result, trace)
        return result


def _stopped(result: InvestigationStopped, trace: RunTrace) -> Exception:
    """The error for a run that ended with no plan. It reads the typed field of the stop and not
    the text of its message."""
    if result.schema_broken:
        return StructuredOutputValidationError(
            MESSAGES.roadmap.stage_run_stopped.format(reason=result.message),
            violations=trace.violations,
        )
    return RoadmapStageError(MESSAGES.roadmap.stage_run_stopped.format(reason=result.message))


__all__ = ["ToolboxClient", "ToolboxModel"]
