# Proposal: #4371

## Why

Issue #4371: the implement ladder differs in three places. The template `k8s/devops/configmap.example.yaml` sets `roadmap.implement.ladder.edit` and `.repair` to `[deepseek-v4.1-flash-1017, claude-sonnet-5-5]` (the second tier came with #4274). The live ConfigMap `devops/devops-cli-config` sets both ladders to `[deepseek-v4.1-flash-1017]`. `k8s/README.md` (Roadmap service, item 19) says "A step has one tier", which matches the live ConfigMap and not the template. A render of the template (`render_active_devops_configmap`) therefore adds a Sonnet tier to the implement job. A prompt of that tier holds repository code and leaves the cluster to Anthropic (SECURITY.md rule 13), at a higher price than a DeepSeek prompt.

The owner decided on 2026-11-09 and 2026-11-10: DeepSeek first, Anthropic models later, after a Sonnet investigation. The slot `analysis` already moved back to DeepSeek on that rule (#4369). The ladders follow the same rule.

## What Changes

- Set `roadmap.implement.ladder.edit` and `.repair` in the template to `[deepseek-v4.1-flash-1017]`, and replace the comment above `implement` with one that names the decision and says that a Sonnet tier is a later trial.
- Add a scenario to the requirement "The implement job runs on a hosted gateway group": each step class of the template has the one tier `deepseek-v4.1-flash-1017`.
- Change the text that stated the second tier: `k8s/README.md` (item 19) and `SECURITY.md` (rule 13).
- Add two tests to `tests/config/test_k8s_devops_runtime.py`: one pins the ladder of the template, one pins the comment.
- Not changed: the code. The ladder setting still accepts more than one tier for a class (#4274), and `docs/roadmap/implement.md` and `docs/ENV_VARS.md` already describe the setting without a Sonnet tier. The live ConfigMap needs no change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: the requirement "The implement job runs on a hosted gateway group" gets a scenario for the one-tier ladder.

## Impact

- `k8s/devops/configmap.example.yaml`, `k8s/README.md`, `SECURITY.md`.
- `tests/config/test_k8s_devops_runtime.py`.
- No cluster change. The live ConfigMap already has one tier, and Argo CD does not own it.

## Feasibility

Read on 2026-11-10.

- `kubectl -n devops get cm devops-cli-config -o jsonpath='{.data.devops-cli\.yaml}'` (read only) prints `roadmap.implement.ladder` with `edit: [deepseek-v4.1-flash-1017]` and `repair: [deepseek-v4.1-flash-1017]`. The template differed before this change, so only the template needs an edit.
- `git show 28356edf` (the merge of #4275 for #4274) shows that the template went from `[deepseek-v4.1-flash-1017]` to the two tiers inside a larger change about Jev and agent configuration. Its proposal says "configure two-tier implement ladders" and gives no measurement, no cost estimate and no owner decision for Sonnet in this job. The README item 19 and the comment of the template before it said "one tier".
- The owner decisions of 2026-11-09 and 2026-11-10 set DeepSeek for every chat slot and move Anthropic models to a later trial after a Sonnet investigation. A Sonnet tier in the ladder is an Anthropic model on the implement job, so the one-tier template is the value that matches the decision. Prices in `k8s/README.md` item 19 show the gap: about 0.002 USD for a DeepSeek call, and Sonnet cost about 67 USD a week in the `analysis` slot (#4369).
- `src/devops_cli/config/settings.py` (`RoadmapImplementConfig`, validator `_check_ladder`) accepts one tier or more for a class, and `tests/config/test_settings.py` pins that. The change keeps that support.
- `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_classes.py tests/config/test_k8s_devops_runtime.py` passes with the one-tier ladder. The group `deepseek-v4.1-flash-1017` is in the `model_list` of `k8s/llm/gateway/config.yaml` and has `max_input_tokens` 1048576, so the window test still passes.

## Existing Tool Considered

No tool is needed: this edits one template, two paragraphs and one test file. The change deletes no internal code.
