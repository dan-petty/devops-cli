# Proposal

## Why

#3880: the stage job of the Service failed every item from 2026-11-06. The task `stage` takes its window from the task `analysis`, and the example ConfigMap sets that window to 65,536 tokens. The first plan request counts about 38,000 tokens, and the hook of the run ends the tools at 49,152 tokens. The run ends its tools after 2 or 3 requests, and the model, which has read almost nothing, answers with the placeholder `x` in every text field. The check refuses the reply, the job sends it back once, the second reply is the same, and the item fails with a list of placeholder faults. That list does not name the window.

## What Changes

- In `k8s/devops/configmap.example.yaml`, set `ai.tasks.analysis.context_window` to 256000, with a comment that gives the reason. The live ConfigMap already holds this value.
- A plan run whose tools the window ends before `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` (8) tool calls raises `RoadmapStageError` at once, whatever the reply is. The message names `ai.tasks.stage.context_window` and the parent `ai.tasks.analysis.context_window`. The job records that error and not the placeholder faults.
- The comment of a staged item no longer has the case "the run offered no tool, because each request reached the limit". A run in that case now fails the item, so the case cannot reach a comment. The branch, its message and its test are deleted.
- A test fails when the planner window of the example ConfigMap is below the minimum that the first request and the minimum tool calls need.
- `docs/roadmap/stage.md` states the window of the Service, and what the model does when the window ends the tools too soon.
- The change has a spec delta in `roadmap-stage`, because the behavior of the stage job and a manifest are observable. The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: REMOVED "The comment states why a run made no tool call"; MODIFIED "The window of the analysis task is documented with its source"; ADDED "The comment states that the model chose no tool", "A plan run whose window ends the tools too soon fails the item" and "The planner window of the example ConfigMap fits a plan run".

## Impact

- Manifests: `k8s/devops/configmap.example.yaml`. This change applies nothing to the cluster. The live ConfigMap already holds `context_window` 256000, applied by hand on 2026-11-07.
- Code: `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_window.py`, `tests/roadmap/test_roadmap_stage_apply.py`.
- Documents: `docs/roadmap/stage.md`.
- The refine and alternatives jobs also read the window of `analysis`. They get the larger window too. Their caps on the body do not grow with it.

## Existing code

- Reuse the hook `_limit_reached` of `src/devops_cli/roadmap/refine_investigation.py`. It already records the limit that ended the tools (`RunTrace.limit`, `RunLimit.WINDOW`), so the new check reads the trace and adds no second measure of the window.
- Reuse `RoadmapStageError`, which the job already records for an item (`_plan_each`).

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| The example ConfigMap sets `ai.tasks.analysis.context_window` to 256000, with a comment | Group 1, for `analysis`. The window of the task `verification` moved to #3911: see Feasibility |
| A plan run whose tools end at the window before a minimum number of tool calls raises `RoadmapStageError` that names the window setting | Group 1 |
| A test fails when the planner window of the example ConfigMap is below the minimum | Group 1 |
| `docs/roadmap/stage.md` states what the model does when the window ends the tools | Group 2 |

## Feasibility

The premise was confirmed against the repository and the evidence of the issue, on `origin/main` at `6d105c20`.

- `git grep -n "context_window" k8s/devops/configmap.example.yaml` shows `analysis` at 65536 and `implement` at 256000. `_TASK_PARENTS` in `src/devops_cli/config/settings.py` is `{"stage": "analysis"}`, so the task `stage` takes the window of `analysis`.
- `tool_stop(window)` in `src/devops_cli/roadmap/refine_investigation.py` is `window - window // 4`: 49,152 tokens for 65,536. The first request counts about 38,000 tokens (the issue measures it on 2026-11-07), so the tools end after a few answers. The runs of the issue made 6 and 4 calls at 65,536 tokens and 40 calls at 262,144 tokens.
- `k8s/llm/gateway/config.yaml` gives the group `deepseek-v4.1-flash-1017` a `max_input_tokens` of 1,048,576. 256,000 tokens is the smallest window of an fp8 provider of the group, as the comment on `implement` says.
- The least number of calls is 8. It is above the 6 calls of the largest failed run and far below the 40 calls of the run that staged.
- The window of the task `verification`: the pull request of #3874 changes the lines of that task in the same file. The task of this pull request says to keep the edit to the `analysis` window, so the two pull requests do not conflict. The verification window moved to #3911.

## Existing Tool Considered

No new tool. The change uses the settings and the hook that exist (`PrepareTools` of pydantic-ai in `src/devops_cli/roadmap/refine_investigation.py`) and the trace of the run. It deletes the stage-comment branch for a run that offered no tool, its message and its test.
