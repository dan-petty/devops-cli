# Proposal

## Why

Issue #1534: The roadmap Service runs intake and refine in the same model lane.
A new P0 or P1 item waits behind every queued refine call before it gets its priority.
This change gives intake its own triage lane on a fast devops-triage model.
A new critical item gets its priority within one poll or delivery.
Refine continues in a separate model lane.

## What Changes

- Add the `devops-triage` model group and its fallback rules to the LLM gateway configuration.
- Add `triage` to `AITasksConfig`, and make intake propose with `ai.for_task("triage")`.
- Add the `triage` service lane with its own clone directory and worker.
- Move intake from the model lane to the triage lane.
- Add the cross-lane refine trigger through `schedule.json` when intake places a P0 item.
- Update documentation and help text to describe three service lanes and the triage model.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: Add `devops-triage` deployment and fallbacks.
- `ai-task-models`: Add `triage` task model override for intake proposal calls.
- `roadmap-scoped-updates`: Run scoped intake on the triage lane.

## Impact

- Roadmap Service runs three worker lanes per repository: status, triage, and model.
- Metrics report queue depth with the `triage` lane label.
- A model-lane round that is blocked does not hold back intake in the triage lane.

## Feasibility

- The LiteLLM gateway configuration in `k8s/llm/gateway/config.yaml` accepts the `devops-triage` deployment on `ollama-64gib-standard` and its fallbacks.
- `tests/test_k8s_llm_gateway.py` validates gateway deployments and routing rules.
- `AITasksConfig` in `src/devops_cli/config/settings.py` validates task overrides and falls back to `ai.model` when unset.
- `src/devops_cli/roadmap/run.py` supports independent lanes through `service_jobs`.
- The cross-lane refine stamp uses `_record_success` under `_SCHEDULE_LOCK` in `schedule.json`.

## Existing Tool Considered

The service uses existing LiteLLM and Ollama infrastructure for model routing.
The service uses existing `RepoWorker` thread management for lane execution.
No custom queue or task runner is built.
Written cost: roughly 60 tokens of new logic, 0 new dependencies, negligible maintenance overhead.
