# Proposal

## Why

The requirement "Every chat model slot of the Service names one model except analysis" in `openspec/specs/roadmap-service-deployment/spec.md` still names `claude-sonnet-5-5` with `context_window` 200000 for `analysis` and `stage`. The template now names `deepseek-v4.1-flash-1017` with `context_window` 256000 for both, and gives `stage` its own entry (#4369, owner decision of 2026-11-10). The change of #4369 set `skip_specs: true`, so no delta updated the spec (#4379).

## What Changes

- A MODIFIED delta replaces the stale requirement and its scenarios with the current template values.
- Sonnet stays only in the requirement that reads the `analysis` comment.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: The chat-slot requirement states the DeepSeek values and the 256000 windows.

## Impact

- Spec: `openspec/specs/roadmap-service-deployment/spec.md`
- Tests: `tests/config/test_k8s_devops_runtime.py` already pins the values and needs no change.

## Feasibility

- The template holds the values.
- The test `test_every_chat_slot_is_deepseek_and_the_stage_slot_is_set_in_the_template` matches them.
- Verification commands: `uv run devops openspec check` and `uv run devops ci test tests/config/test_k8s_devops_runtime.py`.

## Existing Tool Considered

OpenSpec is the tool for the change, and the spec is the only file.
