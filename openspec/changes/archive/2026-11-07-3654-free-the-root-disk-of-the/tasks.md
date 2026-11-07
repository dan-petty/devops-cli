# Tasks

## 1. Write the keep set of each gateway target in the README

Reads: `k8s/llm/gateway/config.yaml`. Changes: `k8s/README.md`, `tests/k8s/test_k8s_ollama_models.py` (new).

- [x] 1.1 Add a table under the GPU Placement section of `k8s/README.md` with one row for each gateway target that serves a model and the models it keeps: `ollama-24gib-embed-gpu0` and `ollama-24gib-embed-gpu1` keep `qwen3-embedding:0.6b`, and `ollama-48gib-fast` and `ollama-64gib-standard` keep `qwen3.8:27b`. Add `tests/k8s/test_k8s_ollama_models.py`: it reads the table and the gateway config with `yaml.safe_load`, builds the set of models of each `api_base` host, and fails with the model and the target when the two differ
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_ollama_models.py` passes
- [x] 1.2 Edit `k8s/README.md` to add the keep-set table of each gateway target under GPU Placement
  - Verification: `$ uv run devops ci docs` passes

## 2. Plan the prune of the models that no tier serves

Reads: `k8s/llm/gateway/config.yaml`, `k8s/llm/profiles/services.yaml`, `src/devops_cli/k8s/gpu_thresholds.py`, `src/devops_cli/config/defaults.py`, `tests/k8s/test_gpu_thresholds.py`. Changes: `src/devops_cli/k8s/ollama_prune.py` (new), `tests/k8s/test_k8s_ollama_prune.py` (new).

- [x] 2.1 Write `tests/k8s/test_k8s_ollama_prune.py` first: `test_a_node_keeps_the_models_of_its_tiers` fails on the base commit because `plan_ollama_prune` does not exist
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_ollama_prune.py` fails on the base
- [x] 2.2 Add `src/devops_cli/k8s/ollama_prune.py`. `gateway_targets(text)` returns the models of each `api_base` host. `service_selectors(text)` returns the selector of each Service. `parse_ollama_list(text)` returns the model names of an `ollama list`. `plan_ollama_prune(gateway, services, pods, listed)` returns one entry for each node with its keep set, the models to remove, and the nodes whose list failed. A pod matches a Service when its labels hold the selector, so a node with two tiers keeps one copy of a shared model, and a failed list removes nothing and names the node
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_ollama_prune.py` passes

## 3. Add the ollama prune command

Reads: `src/devops_cli/commands/k8s/volume.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/dry_run/requests.py`, `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/k8s/ollama_prune.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/k8s/test_k8s_volume_reclaim.py`. Changes: `src/devops_cli/commands/k8s/ollama.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/k8s/test_k8s_ollama_prune.py` (new), `k8s/README.md`.

- [x] 3.1 Write `tests/commands/k8s/test_k8s_ollama_prune.py` first: `test_dry_run_makes_no_cluster_call` and `test_a_failed_ollama_list_stops_the_node` fail on the base commit because the command does not exist
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_ollama_prune.py` fails on the base
- [x] 3.2 Add `devops k8s ollama prune` in `src/devops_cli/commands/k8s/ollama.py` with `--plan`, `--dry-run` and `--context`, declared `@dry_run_class("request-plan")` as `src/devops_cli/commands/k8s/volume.py:59:@dry_run_class("request-plan")` is. It reads the two manifests through the defaults of `src/devops_cli/config/defaults.py`, lists the Ollama pods with `kubectl`, runs `ollama list` in one pod of each node, prints the plan, and runs `ollama rm` for each model of the plan. A node whose list fails removes nothing, is named, and exits 1. `--dry-run` prints the `kubectl exec` commands of each gateway target and calls nothing. Register the group in `src/devops_cli/commands/k8s/__init__.py`, and add the heading to `src/devops_cli/config/constants.py`, the help to `HELP.k8s` and the messages to `MESSAGES.k8s`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_ollama_prune.py` passes
- [x] 3.3 Edit `k8s/README.md` to document `devops k8s ollama prune`, `--plan` and `--dry-run` under GPU Placement, and run `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The root filesystem of the control-plane node is under 75% used., Only a person runs the prune on the homelab node and reads the used fraction of its root filesystem; #3660 records that check.
- Pending person: `LocalPathNodeDiskHigh` does not fire for this node for 7 days., Only a person watches the live alert for 7 days after the prune; #3660 records the query and the result.
- Group 1: Each model that the tiers of this node need stays available, and the fix writes down which models the node keeps.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
