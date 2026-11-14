# Proposal

## Why

The caps of the stage planner were set by guess: the lines and characters of a tool answer, the commits of `git_log`, and the files of `repo_map`. The telemetry of #3240 records the size of an answer after the cut, so a cut answer looks like a short answer, and the project cannot tell which cap cuts a useful answer. This change adds the missing cut signal, so a later item can set each cap from one week of data (#3241).

## What Changes

- `cut_with_cap` in `src/devops_cli/roadmap/refine/refine_investigation.py` returns the cut text and the name of the cap that cut it, or None. The existing `cut` delegates to it, so its callers stay unchanged.
- The stage tools mark a cut answer with the cap name in the metadata of their `ToolReturn`: `lines`, `chars`, `spec`, `log` or `map`. An answer that no cap cut keeps the `ToolOutcome.OK` metadata.
- `git_log` requests one more commit than `CONST_ROADMAP_STAGE_LOG_MAX_COUNT` so that it can tell a full history from a longer one.
- `ToolCallRecord` records the cap that cut the answer of the call, or None.
- `end_run` in `src/devops_cli/roadmap/tool_metrics.py` adds 1 to `devops_cli_roadmap_tool_cuts_total` for each cut answer with the labels tool, row, toolset and cap.
- The instrument is declared in `src/devops_cli/telemetry/instruments.py` and listed in `docs/TELEMETRY.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: The cut counter is a declared instrument and the document lists it.

## Impact

- Code: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/tool_metrics.py`, `src/devops_cli/telemetry/instruments.py`
- Documents: `docs/TELEMETRY.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_tools.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/ai/client/test_roadmap_agent_run.py`

## Feasibility

- `cut` in `refine_investigation.py` already drops lines and characters and sets one notice. The change adds the name of the limit that fired, and `cut` keeps its text result.
- `_outcome_of` in `agent_run.py` already reads a mapping metadata, so a `cut` key needs one branch and one field of `ToolCallRecord`.
- `end_run` already sends one metric for each call of the trace.
- Verification commands: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `uv run devops ci test tests/ai/client/test_roadmap_agent_run.py`, and `uv run devops ci docs`.

## Existing Tool Considered

No open, maintained tool attributes a cut to one cap of this repository. Langfuse records traces and token use, and pydantic-ai-harness limits tool output at run time for another framework. The change adds one metadata key, one trace field, one counter and tests.
