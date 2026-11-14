# Tasks

## 1. Mark cut answers and count them

Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/tool_metrics.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`. Changes: the same files and the named tests.

- [x] 1.1 In `src/devops_cli/roadmap/refine/refine_investigation.py`, add `cut_with_cap(lines, *, max_chars=CONST_ROADMAP_REFINE_TOOL_MAX_CHARS, char_cap=CAP_CHARS) -> tuple[str, str | None]` with the body of `cut`, and define `CAP_LINES = "lines"` and `CAP_CHARS = "chars"`. A line cut returns `CAP_LINES`; a character cut returns `char_cap`. Keep `cut` as a wrapper that returns the text.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py -k cut` passes
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_tools.py`, add `_capped(lines, *, max_chars=CONST_ROADMAP_REFINE_TOOL_MAX_CHARS, char_cap=CAP_CHARS) -> ToolReturn` that returns `ok_answer(text)` when no cap cut and a `ToolReturn` with metadata `{"outcome": ToolOutcome.OK, "cut": cap}` otherwise. Replace each `ok_answer(cut(...))` with `_capped(...)`, use `char_cap="spec"` in `read_spec`, request `CONST_ROADMAP_STAGE_LOG_MAX_COUNT + 1` commits in `git_log` and mark a longer history with `log`, and mark `repo_map` with `map` when it leaves files out.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` passes
- [x] 1.3 In `src/devops_cli/roadmap/agent_run.py`, add `cut: str | None = None` to `ToolCallRecord`, return the `cut` key from `_outcome_of`, and keep it in `RunTrace._add_reply`.
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py` passes
- [x] 1.4 In `src/devops_cli/telemetry/instruments.py`, declare `ROADMAP_TOOL_CUTS_TOTAL` as the counter `devops_cli_roadmap_tool_cuts_total`, add it to the registry and to `__all__`. In `src/devops_cli/roadmap/tool_metrics.py`, emit 1 for each record whose `cut` is not None. Update `docs/TELEMETRY.md`.
  - Verification: `$ uv run devops ci docs` passes
- [x] 1.5 Add the tests: a long answer names its cap and a short one names none, `git_log` and `repo_map` name their caps, `RunTrace.absorb` keeps the cap, and `end_run` emits one count for a cut call and none for a whole call in `tests/roadmap/stage/test_roadmap_stage_tools.py`, `tests/ai/client/test_roadmap_agent_run.py`, and `tests/roadmap/stage/test_roadmap_stage_toolbox.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py tests/ai/client/test_roadmap_agent_run.py tests/roadmap/stage/test_roadmap_stage_toolbox.py` passes
