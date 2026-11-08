"""The planner client that calls the read-only tools (#3037).

`ToolboxClient` implements `StageClient`, so the planner, the gates and the golden-set run keep
their code. A call for a `StageProposal` is one agent run with the tools of `StageTools`: the nine of
the toolset `base`, and with `extended`, the setting `roadmap.stage.toolset`, three more (#3238). A
call for a `Verification` is one agent run of the same tools, with the pass as its instructions and
no text or message of the planner (#3039). A call for another schema goes to the inner client, with
no tool. Each run has a new budget of tool calls and requests, ends its tools when the messages
fill the context window (#3037), and keeps a `RunTrace` of what it did. It sends the counts of the
run as metrics (`tool_metrics`, #3240). The output tokens have no count of their own (#3206). A run
that ends with no reply raises `RoadmapStageError` and names the limit it hit, or
`StructuredOutputValidationError` when the model broke the schema of its reply past its retries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_MAX_REQUESTS,
    CONST_ROADMAP_STAGE_MIN_TOOL_CALLS,
    CONST_ROADMAP_STAGE_TOOL_MAX_CALLS,
)
from devops_cli.config.defaults import StageToolset
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.agent_run import RunLimit, RunTrace
from devops_cli.roadmap.refine.refine_investigation import InvestigationStopped, investigate
from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_github import StageGitHub
from devops_cli.roadmap.stage.stage_tools import StageTools
from devops_cli.roadmap.stage.stage_verify import (
    Finding,
    Verification,
    VerificationInput,
    agent_instructions,
    verify,
)
from devops_cli.roadmap.tool_metrics import end_run, start_run

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage import StageClient

TOOLS_TASK = "roadmap_stage_tools.md"
EXTENDED_TOOLS_TASK = "roadmap_stage_tools_extended.md"
# The schemas that one agent run with the tools answers, a plan (#3037) and a verification (#3039),
# with the job row of each in the metrics of the tool calls (`row` label, #3240). The rows differ,
# so the reads of the verifier do not hide a tool that the planner does not use.
_AGENT_ROWS: Final[Mapping[type[BaseModel], str]] = {
    StageProposal: "stage",
    Verification: "stage_verify",
}


@dataclass(frozen=True)
class ToolboxModel:
    """The pydantic-ai model of an agent run that has the tools. Give it where the job takes a
    model to ask for a plan or a review with the toolbox; a client instead plans with the one call
    and no tool."""

    model: Any


class ToolboxClient:
    """A stage client whose plan runs and review runs read the repository at `sha` with read-only
    tools.

    `model` is the pydantic-ai model of the run, and `inner` answers every call that is not for a
    plan or a review. `traces` holds one `RunTrace` for each of these runs, in order; the caller
    clears it. With a `window`, the context window of the model in tokens, a request that would
    leave too little of it for the reply offers no tool. `openspec` reads the specs for `read_spec`. `toolset` is
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
        traces: list[RunTrace] | None = None,
    ) -> None:
        self._model = model
        self._inner = inner
        chosen = toolset or load_settings().roadmap.stage.toolset
        self._tools = StageTools(
            source=source, sha=sha, openspec=openspec, toolset=chosen, github=github
        )
        self._instructions = load_task_prompt(TOOLS_TASK)
        if chosen == "extended":
            self._instructions += f"\n\n{load_task_prompt(EXTENDED_TOOLS_TASK)}"
        self._window = window
        self._toolset = chosen
        self._tool_names = tuple(tool.name for tool in self._tools.tools())
        # A caller that wants the runs of two clients in one order passes one list to both (#3039).
        self.traces: list[RunTrace] = [] if traces is None else traces
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
        """The reply of one agent run for `StageProposal` or `Verification`, or the inner client's
        reply for any other schema."""
        if schema not in _AGENT_ROWS:
            return self._inner.chat_structured(system, prompt, schema, max_retries=max_retries)
        # The planner reads the rules of its tools with its plan. A review gets only its own pass
        # as its instructions, with no text of the planner (#3039).
        instructions = (
            f"{system}\n\n{self._instructions}"
            if schema is StageProposal
            else agent_instructions(system)
        )
        trace = RunTrace()
        self.traces.append(trace)
        row = _AGENT_ROWS[schema]
        start_run(self._tool_names, row=row, toolset=self._toolset)
        finished = False
        try:
            result = investigate(
                self._model,
                instructions,
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
            end_run(trace, row=row, toolset=self._toolset, finished=finished)
        if self._window_starved(trace):
            template = (
                MESSAGES.roadmap.stage_window_starved
                if schema is StageProposal
                else MESSAGES.roadmap.stage_verify_window_starved
            )
            raise RoadmapStageError(
                template.format(
                    window=self._window,
                    calls=len(trace.tool_calls),
                    minimum=CONST_ROADMAP_STAGE_MIN_TOOL_CALLS,
                )
            )
        if isinstance(result, InvestigationStopped):
            raise _stopped(result, trace, schema)
        return result

    @staticmethod
    def _window_starved(trace: RunTrace) -> bool:
        """Whether the window ended the tools of the run before the least number of tool calls
        (#3880). The model then writes its plan about code that it did not read, and the
        placeholders in the plan hide the cause. A review run that the window starves has read
        almost none of the code too, so it fails too (#3911)."""
        return (
            trace.limit is RunLimit.WINDOW
            and len(trace.tool_calls) < CONST_ROADMAP_STAGE_MIN_TOOL_CALLS
        )


def _stopped(result: InvestigationStopped, trace: RunTrace, schema: type[BaseModel]) -> Exception:
    """The error for a run that ended with no reply: a plan run, or a review run of a plan that
    already passed the gates. It reads the typed field of the stop and not the text of its
    message."""
    template = (
        MESSAGES.roadmap.stage_run_stopped
        if schema is StageProposal
        else MESSAGES.roadmap.stage_verify_stopped
    )
    message = template.format(reason=result.message)
    if result.schema_broken:
        return StructuredOutputValidationError(message, violations=trace.violations)
    return RoadmapStageError(message)


def review(
    client: ToolboxClient, given: VerificationInput
) -> tuple[list[Finding], VerificationInput]:
    """The findings of one agent run on `given`, and `given` with the tool answers of that run, so
    a quote of what the run read counts as evidence (#3039)."""
    findings = verify(client, given)
    return findings, given.with_reads(client.traces[-1].tool_answers)


__all__ = ["ToolboxClient", "ToolboxModel", "review"]
