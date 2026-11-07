# Proposal

## Why

#3911: the example ConfigMap (`k8s/devops/configmap.example.yaml`) sets no `context_window` for the task `verification`. That task has no parent task, so it takes the default window of 32,768 tokens. The verification pass is an agent run with the read tools of the planner. The run hook ends its tools at three quarters of the window, which is 24,576 tokens. A plan whose review needs many tool calls ends its tools early, and the review then reads almost none of the code. This is the same cause as #3880, for the review run. #3880 fixed the planner window only, because the pull request of #3874 edited the lines of the task `verification` in the same file.

A review that read almost none of the code gives findings that nobody can trust, and a plan with no finding stages as clean. So a review run that the window starves must fail the item, as a plan run does.

## What Changes

- In `k8s/devops/configmap.example.yaml`, set `ai.tasks.verification.context_window` to 256000, with a comment that gives the reason. The window is the same as for the task `analysis`, and the model is the same group (#3874).
- A review run whose tools the window ends before `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` (8) tool calls raises `RoadmapStageError`, as a plan run does. The message names `ai.tasks.verification.context_window`. This is the decision on a failed review run: it fails the item, and it is not advice.
- A test fails when the verification window of the example ConfigMap is below what the first request of a review and the least tool calls need.
- `docs/roadmap/stage.md` states the window of the task `verification` and the failure.
- The change has a spec delta in `roadmap-stage`, because the behavior of the stage job and a manifest are observable. The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: MODIFIED "A plan run whose window ends the tools too soon fails the item" (a review run fails too); ADDED "The review window of the example ConfigMap fits a review run".

## Impact

- Manifests: `k8s/devops/configmap.example.yaml`. This change applies nothing to the cluster. A person applies the live ConfigMap (#3903).
- Code: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`.
- Documents: `docs/roadmap/stage.md`.
- The refine job reads no tool in its review, and the stage eval of the verification pass reads the window of the task `verification` too. Both get the larger window.

## Existing code

- Reuse `ToolboxClient._window_starved`, the trace of the run (`RunTrace.limit`) and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` from #3880. The change adds one message and removes the condition `schema is StageProposal`.
- Reuse `tool_stop`, `tokens_of` and `agent_instructions` in the test, so the test counts the first request as the run hook counts it.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| The example ConfigMap sets `ai.tasks.verification.context_window` to 256000, with a comment | Group 1 |
| A test fails when the verification window of the example ConfigMap is below the least window of a review run | Group 1 |
| The decision on a failed review run whose window ends its tools too soon is recorded | Group 1 (it fails the item) and `design.md` |

## Feasibility

The premise was confirmed against the repository on `origin/main` at `2be237be`.

- `git grep -n "context_window" k8s/devops/configmap.example.yaml` showed `analysis` and `implement` at 256000 and no window for `verification`.
- `_TASK_PARENTS` in `src/devops_cli/config/settings.py` is `{"stage": "analysis"}`, so the task `verification` has no parent. `task_window("verification")` in `refine_investigation.py` then returns the window of `ai`, `DEFAULT_AI_CONTEXT_WINDOW` (32,768), and the example ConfigMap sets none at the `ai` level.
- `tool_stop(window)` is `window - window // 4`: 24,576 tokens for 32,768. The test counts the first review request (body at its cap, a plan, and the instructions) plus 8 tool answers of 2,000 tokens, and 24,576 is below that sum. On the base the test fails.
- `k8s/llm/gateway/config.yaml` gives the model group `deepseek-v4.1-flash-1017` a `max_input_tokens` of 1,048,576. 256,000 tokens is the smallest window of an fp8 provider of the group (#3880). The pull request of #3874 is merged, so the task `verification` names the same model as `analysis`.
- Before this change, a review run that the window starved did not fail (a test said so). No other code needs a change: the stage job already records a `RoadmapStageError` for the item.

## Existing Tool Considered

No new tool. The change uses the settings, the run hook of pydantic-ai (`PrepareTools` in `refine_investigation.py`) and the trace that exist. It deletes the condition that limits the window check to a plan run.
