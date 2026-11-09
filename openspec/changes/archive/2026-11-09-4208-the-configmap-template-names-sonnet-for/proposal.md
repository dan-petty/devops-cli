# Proposal

## Why

On 2026-11-09 the owner decided to try `claude-sonnet-5-5` in the `analysis` slot, because the stage job stages nothing with `deepseek-v4.1-flash-1017` (#4204). A person changed the live ConfigMap `devops-cli-config` by hand: `ai.tasks.analysis.model` is `claude-sonnet-5-5` and `ai.tasks.analysis.context_window` is `200000`. The template `k8s/devops/configmap.example.yaml` still names DeepSeek with 256000. A `deploy-stack` renders the template, so the next deploy puts DeepSeek back and ends the trial with no decision. The cluster is git, so a hand change that the repository does not hold is lost (#4208).

## What Changes

- Change `ai.tasks.analysis` in `k8s/devops/configmap.example.yaml` to `model: claude-sonnet-5-5` and `context_window: 200000`, with a comment that gives the reason (#4204), the owner and the date (2026-11-09), the cost (about 0.27 USD for each stage case at the sample of #3566, and the stage row takes up to 3 items for each 37 minutes) and the way back (the one-model rule of #3874 applies again).
- Keep every other slot as it is: `ai.model`, `implement`, `verification`, `chat` and `triage` stay `deepseek-v4.1-flash-1017`, and `embedding` stays `qwen3-embedding:0.6b`. Fix the header comment of the model block and the comment of `verification`, which say that one model serves every slot and that the window is the same as for `analysis`.
- Modify the requirement "Every chat model slot of the Service names one model" of `roadmap-service-deployment` to name the one exception, `analysis`, and rename it to say so. This is an observable change: a manifest and the model that serves the planner.
- Change the tests that pin the old state. `tests/config/test_k8s_devops_runtime.py` gets a test of the new slot and of its comment. `tests/k8s/test_k8s_configmap.py` takes the exception `analysis`. `tests/roadmap/stage/test_roadmap_stage_window.py` takes the window 200,000 and the gateway window 1,000,000 of Sonnet, and no longer says that the review and the planner share a model.
- Fix the documents that name the old state: item 19 of `k8s/README.md` and the sentence on `analysis` near it, the paragraph on the window of the task `stage` in `docs/roadmap/stage.md`, and rule 13 of `SECURITY.md`, which names DeepSeek for every chat slot and says that `claude-sonnet-5-5` serves no slot. The prompts of `analysis` then leave the cluster to Anthropic and not to OpenRouter.
- This PR applies nothing to the cluster: the live ConfigMap already holds these values (applied by hand on 2026-11-09).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: The requirement "Every chat model slot of the Service names one model" names the exception `analysis`.

## Impact

- Manifests: `k8s/devops/configmap.example.yaml`
- Documents: `k8s/README.md`, `docs/roadmap/stage.md`, `SECURITY.md`, `openspec/specs/roadmap-service-deployment/spec.md` (by the delta)
- Tests: `tests/config/test_k8s_devops_runtime.py`, `tests/k8s/test_k8s_configmap.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`

## Feasibility

Confirmed on 2026-11-09 against the real system and the repository:

- The live ConfigMap matches the issue. A read-only `kubectl get configmap devops-cli-config -n devops` shows `ai.tasks.analysis` with `claude-sonnet-5-5` and `context_window` 200000. `ai.model`, `implement`, `verification`, `chat` and `triage` show `deepseek-v4.1-flash-1017`, and `embedding` shows `qwen3-embedding:0.6b`. The template on `origin/main` (d37762b6) still names DeepSeek and 256000 for `analysis`, so the drift is real.
- The gateway serves the group. `k8s/llm/gateway/config.yaml` holds `model_name: claude-sonnet-5-5` with `max_input_tokens: 1000000`, which is not below 200000, and a fallback of that group to `deepseek-v4.1-flash-1017`. `CONST_AI_GATEWAY_HOSTED_MODELS` in `src/devops_cli/config/constants.py` lists `claude-sonnet-5-5`, so the settings accept it.
- No merged change or open pull request did this work: a search of pull requests for #4208 found none. #3874 is closed and is the rule that the trial departs from. #4204 is open and is the reason.
- The key-walk test of #4093 (`tests/k8s/test_k8s_configmap_keys.py`) walks keys and not values. `model` and `context_window` are declared settings, so the test holds.
- The limit of the stage planner (150,000 tokens at the window 200,000) still fits the first request plus the minimum tool calls that `tests/roadmap/stage/test_roadmap_stage_window.py` computes.
- Cost source: the 0.27 USD for each stage case is the figure of the issue body (#4208); no comment on #3566 holds a figure, so the issue is the source.
- Precondition: the read-only `kubectl` call needs a client of the cluster.

## Existing Tool Considered

None needed. The change edits one YAML template, one spec requirement, three documents and three tests. `devops k8s deploy-stack` and Argo CD already apply the template. The code that it deletes: the claim in the template, the spec, the README and `SECURITY.md` that every chat slot names DeepSeek.
