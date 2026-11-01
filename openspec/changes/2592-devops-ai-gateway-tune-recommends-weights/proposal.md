# Proposal

## Why

Issue #2592: `devops ai gateway tune` recommends a routing weight and a concurrency for each deployment. It tells the reader to set `litellm_params.weight`. The gateway routes with `least-busy`, which reads no weight, and no deployment sets `weight` or `max_parallel_requests`. The reader can not apply the advice. This change makes the command report what it measures and nothing more.

## What Changes

- The table of `devops ai gateway tune` loses the columns Weight, Recommended and Max Parallel. Its footer no longer says to set `litellm_params.weight`. It says that the gateway routes with `least-busy` and reads none of the numbers.
- The help text of the command says that it measures and reports.
- The JSON report loses `recommended_weight` and `recommended_concurrency` of each deployment.
- `recommend_weights`, `calculate_hardware_weights`, `calculate_hardware_concurrency` and their private helpers are deleted from `src/devops_cli/ai/gateway_tune.py`, with their five constants and their tests. The module docstring names `least-busy`, not `simple-shuffle`.
- `tune_pool` loses its two parameters `overrides` and `concurrency_overrides`.
- The setting `ai.gateway_weights` is deleted, because only `tune_cmd` read it. A config file that still holds it gets the usual error of a refused key, with the command `devops config unset ai.gateway_weights`.
- The setting `ai.gateway_concurrency` stays (see Feasibility). Four tests that used `ai.gateway_weights` as their example of a mapping setting use `ai.gateway_concurrency`, and two requirements of `config-commands` name it in the same way.
- `k8s/README.md` and the generated documents are corrected.

The change alters what a consumer observes (the output of a command and a setting), so it carries spec deltas: `gateway-tuning` (ADDED) and `config-commands` (MODIFIED, two requirements whose scenarios named `ai.gateway_weights`). The change fits one pull request.

## Capabilities

### Modified Capabilities

- `gateway-tuning`: the tune report recommends no weight and no concurrency; `ai.gateway_weights` does not exist.
- `config-commands`: the examples of a mapping setting are `ai.gateway_concurrency`, not `ai.gateway_weights`.

## Acceptance

The issue has no acceptance list. Its "Expected" text and its "Proposed design" give these criteria.

| Criterion | Delivered by |
| :--- | :--- |
| The table has no weight or concurrency column | Group 1 |
| The footer does not say to set `litellm_params.weight` | Group 1 |
| The help text and the generated command documents do not say "recommend routing weights" | Group 1 (help, documents) |
| The module docstring names `least-busy`, not `simple-shuffle` | Group 2 |
| `recommend_weights`, `calculate_hardware_weights` and `calculate_hardware_concurrency` are gone | Group 2 |
| `ai.gateway_weights` is gone | Group 4 |
| `ai.gateway_concurrency` is gone | Not delivered. The RAG embedder reads it (see Feasibility). This is a correction of the refine design, which said that no code reads it. |

## Feasibility

Checked on 2026-11-01 against `origin/main` (`0d2d0723`).

- The gateway routes with `least-busy` and sets no weight. `git grep -n routing_strategy k8s/llm/gateway/config.yaml` prints `216:  routing_strategy: least-busy` and `223:      routing_strategy: simple-shuffle`. Line 223 is the `embedding` routing group only. `git grep -nE "^\s*(weight|max_parallel_requests|rpm|tpm):" k8s/llm/gateway/config.yaml` prints nothing.
- LiteLLM reads `weight` only under `simple-shuffle`. The routing page of the LiteLLM documentation (docs.litellm.ai/docs/routing) says that weights work "across simple-shuffle routing strategy", and describes `least-busy` as "the least number of ongoing calls". The gateway image is `ghcr.io/berriai/litellm:v1.103.0` (`k8s/llm/gateway/deployment.yaml:33`).
- The tune command cannot serve the `embedding` group, the one group with `simple-shuffle`. `src/devops_cli/ai/gateway_bench.py:51` posts to `{base}/chat/completions`, and the embedding model has no chat API. So no group that the command measures reads a weight.
- The text of the issue is on `origin/main`. `src/devops_cli/commands/ai_gateway.py` holds the headers at lines 475-487, the row values at 501-503, the footer at 520 and the help line at 584. `src/devops_cli/ai/gateway_tune.py` holds the docstring at lines 1-4, the fields `recommended_weight` and `recommended_concurrency` at 112-113 and the functions at 154-292 (`_deployment_bandwidth_sum` at 211 stays). The tune call passes the two settings at `ai_gateway.py:640-641`.
- Nothing newer did it. `git log -1 origin/main -- src/devops_cli/ai/gateway_tune.py` is `efd61596` (2026-10-31, an unrelated dry-run change). The document issue #1971 is closed. `k8s/README.md:133` already says that the gateway uses neither number, but it still says that the command prints them.
- Nothing else reads `ai.gateway_weights`. `git grep -n gateway_weights -- src` prints `settings.py:667`, `ai_gateway.py:640` and a docstring in `config/round_trip.py:68`. The rest are tests (`tests/config/test_config_key_removal.py`, `test_config_keys.py`, `test_config_save_round_trip.py`, `tests/commands/test_config_field_validation.py`), two scenarios of `openspec/specs/config-commands/spec.md` (lines 109-110 and 213) and the generated `docs/CONFIGURATION.md:212`.
- The refine claim about `ai.gateway_concurrency` is wrong. `git grep -n gateway_concurrency -- src` prints `src/devops_cli/ai/rag/embeddings.py:1158` and `src/devops_cli/ai/rag/indexer.py:421`. Both read `ai.gateway_concurrency["embedding"]` to size the embedding batches. The setting is live, so this change keeps it. This is the one place where the plan does less than the refine design asked.
- The five constants (`CONST_CONTINUOUS_BATCHING_ENGINES`, `CONST_ENGINE_MULTIPLIER_CONTINUOUS_BATCHING`, `CONST_ENGINE_MULTIPLIER_SERIAL`, `CONST_DEFAULT_CONTINUOUS_CONCURRENCY`, `CONST_DEFAULT_SERIAL_CONCURRENCY`) are used only in `gateway_tune.py` (`git grep -n CONST_ENGINE_MULTIPLIER -- src tests`). They become dead and the plan deletes them.
- `_dep_field` and `_deployment_bandwidth_sum` stay. `estimate_deployment` calls them (`gateway_tune.py:698-699`).
- `ai.gateway_weights` is in no table of removed keys. `CONST_REMOVED_CONFIG_KEYS` (`src/devops_cli/config/constants.py:59`) names a release for each key, and the plan does not name a release before it exists. The error of a refused key works without one: it names the file, the line and the unset command (`tests/config/test_unknown_config_keys.py`).
- No other active change touches `gateway-tuning` or `config-commands` (`ls openspec/changes/*/specs`).

## Existing Tool Considered

The LiteLLM routing documentation covers the need: `least-busy` picks the deployment with the fewest calls in flight and reads no weight. Nothing new is built. The change deletes the weight and concurrency recommendation (`recommend_weights`, `calculate_hardware_weights`, `calculate_hardware_concurrency`, `_resolve_override`, `_deployment_backend_map`, `_is_continuous_engine`, `_deployment_hardware_score`), their five constants, the two `tune_pool` parameters, the two fields of `DeploymentTune`, the setting `ai.gateway_weights` and their tests.
