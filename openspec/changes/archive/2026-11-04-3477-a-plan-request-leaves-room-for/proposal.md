# Proposal

## Why

The stage planner made no tool call in 38 of 38 plan runs since 2026-11-02 (#3477). The first request counted 51,907 to 78,428 tokens for nine open items. The run hook offers no tool when the messages and one quarter of the window reach the window, and the planner window is 65,536 tokens, so the limit is 49,152 tokens. The first request was over the limit, the first reply of the model was the output tool, and the model wrote facts about code that it did not read.

The parts of the request were the capabilities as plain JSON (27,910 tokens for 172 capabilities), a repository context capped at half of the window (32,768 tokens) and a body capped at one quarter of the window (16,384 tokens).

## What Changes

- The context of the first plan request has a fixed cap of 20,480 tokens, and the body has a fixed cap of 8,192 tokens. A cap is also at most its share of a small window. A larger window gives no larger cap.
- A plan run that has `read_spec` gets the names of the capabilities in the first request, and reads the purpose and the requirement names of one capability on demand. A run with no tool keeps the full entries.
- `read_spec` gives the purpose of a capability, from the `overview` field of `openspec show --json`, before the requirement names.
- The first request with the context and the body at their caps leaves at least 8,192 tokens below the tool-removal limit.
- `RunTrace` records the names of the tools that each model request offered.
- The stage comment of a run with no tool call states the reason: the run offered no tool because each request reached the tool-removal limit, or the run offered tools and the model called none.
- The page `docs/roadmap/stage.md` states the `context_window` of the task `analysis`, its source, the `max_input_tokens` of its model, and the caps.
- A test measures the refine investigation request against the same limit and prints the counts. Refine does not change.
- The change adds no metric (#3240 owns the metrics). The live run on five Ready items is #3489.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The first plan request leaves room for the tools, the run trace records the offered tools, and the comment states why a run made no tool call

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/stage.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_tools.md`
- Tests: `tests/roadmap/test_roadmap_stage_window.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_tools.py`, `tests/roadmap/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_limit_classes.py`

## Feasibility

- The measure at `origin/main` confirms the premise. For the nine open items, the first request, built with `collect_context`, `probe_premise` and `read_base_specs` on this checkout, counts 36,153 to 69,689 tokens, and the prompts add 4,187 tokens. Five of the nine requests are over 49,152 tokens, and the other four stay near the limit.
- The capabilities as plain JSON count 27,910 tokens for 172 capabilities. Their names count 1,117 tokens. With the names only, the request at the caps counts about 34,000 tokens.
- The source confirms the limit. `_within_window_of` in `src/devops_cli/roadmap/refine_investigation.py` offers no tool when `_tokens_of(messages) + window // 4 >= window`. The setting `ai.tasks.analysis.context_window` is 65536 in `k8s/devops/configmap.example.yaml`, so the limit is 49,152 tokens.
- A scripted model through the real hook shows the fault. A plan request with the context and the body at the old caps (32,768 and 16,384 tokens) offers no tool, and the new test fails on the base for this reason.
- The openspec tool confirms the source of a purpose. `openspec show roadmap-stage --type spec --json` prints an `overview` field that holds the Purpose text.
- The items #3246, #3258 and #3428 add context to the same request. All three are open, and no open pull request names them. Their text goes into `context`, which has the fixed cap, so each one fits the bound when it merges. None of them may add a key to the request outside `context` without a measure.
- The refine investigation request counts 31,415 tokens for an item with a body of 8,192 tokens and three replies of 1,000 tokens, which is below the limit. With 10 replies at their cap of 4,096 tokens, it counts 66,411 tokens, which is over the limit. This change does not alter refine. The test prints both counts.

## Existing Tool Considered

pydantic-ai `PrepareTools` already holds the hook, and `read_spec` already exists. The change adds no tool and no library. The cost is about 25,000 tokens to build, about 2,000 tokens to keep and fix, and about 3 hours.

## Dependencies

None.
