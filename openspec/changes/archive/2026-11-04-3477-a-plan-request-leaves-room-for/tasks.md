# Tasks

## 1. Record the tools that each request offered

Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`.

- [x] 1.1 Add tests to `tests/roadmap/test_roadmap_stage_toolbox.py`: the trace of a scripted run that loses its tools holds the tool names of each request and an empty entry for the last one, and `RunTrace.combined` joins the entries of two traces in order
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py` fails on the base
- [x] 1.2 Add the field `offered` to `RunTrace`, join it in `combined`, and take it in `absorb`. Wrap the hook of `investigate` so that it records the names of the tools it offers for each request, and pass them to `trace.absorb`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_refine_investigation.py` passes

## 2. Cap the first plan request and deliver the capabilities on demand

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_stage_tools.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_tools.md`, `tests/roadmap/test_roadmap_stage_window.py`, `tests/roadmap/test_roadmap_stage_tools.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 2.1 Add `tests/roadmap/test_roadmap_stage_window.py`: the first request with the context and the body at their caps offers `read_spec` and stays `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` below the limit, the caps do not grow at a window of 1048576 tokens, a window of 8192 tokens cuts them to its shares, the first request names 170 capabilities and holds no purpose, and the context with the longest `read_spec` answer stays under half of the window. Change `tests/roadmap/test_roadmap_stage_tools.py` so that `read_spec` of one capability answers with its purpose first. Add the three constants to the table of `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_window.py tests/roadmap/test_roadmap_stage_tools.py` fails on the base
- [x] 2.2 Add `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS`, `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` and `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` to `src/devops_cli/config/constants.py`. In `_Planner._request` cap the context and the body at the smaller of the constant and the share of the window. Add `ToolboxClient.reads_specs` and send the names of the capabilities when the client has it. Give the purpose in the answer of `read_spec` for one capability. State both in the two planner prompts
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_window.py tests/roadmap/test_roadmap_stage_tools.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 3. State why a run made no tool call

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [x] 3.1 Add tests to `tests/roadmap/test_roadmap_stage_apply.py`: the comment of a run on a window of 100 tokens says that the run offered no tool because each request reached the tool-removal limit, and the comment of a run that offered its tools says on how many requests it offered them and that the model called none
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` fails on the base
- [x] 3.2 Add the two sentences to the messages table and choose between them in `_run_report` from `trace.offered`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` passes

## 4. Measure the refine request and document the window

Reads: `docs/roadmap/stage.md`, `tests/roadmap/test_roadmap_refine_investigation.py`. Changes: `docs/roadmap/stage.md`, `tests/roadmap/test_roadmap_refine_investigation.py`.

- [x] 4.1 Add a test to `tests/roadmap/test_roadmap_refine_investigation.py` that builds the first refine investigation request at a window of 65536 tokens, prints its count and the limit of 49152 tokens, and asserts that the request of a large item is under the limit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_investigation.py` passes
- [x] 4.2 Add the section "The window of the plan run" to `docs/roadmap/stage.md`: the `context_window` of `analysis` with its file, the `max_input_tokens` of its model with its file, the caps, and the trace. The test in `tests/roadmap/test_roadmap_stage_window.py` reads the page against the two files. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- #3489 runs the live check on five Ready items.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
