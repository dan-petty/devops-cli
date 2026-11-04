# Tasks

## 1. Render the tiers from the thresholds (behavior)

- [x] 1.1 Write the failing tests of the thresholds, the names, the instances, the refusals and the CLI.
  Verification: `uv run devops ci test tests/k8s/test_gpu_thresholds.py`
- [x] 1.2 Add `src/devops_cli/k8s/gpu_thresholds.py`, and call it from `devops ai gateway render` with `--thresholds` and `--tier-templates`.
  Verification: `uv run devops ci test tests/k8s/test_gpu_thresholds.py tests/ai/test_ai_gateway_render.py`

## 2. Move the tracked manifests (manifests)

- [x] 2.1 Add `gpu-thresholds.yaml` and `tier-templates/ollama-48gib-slow.yaml`, add the markers, and delete the hand-written `ollama-48gib-slow` DaemonSet and Service. Run `uv run devops ai gateway render --apply`.
  Verification: `uv run devops ai gateway render`
- [x] 2.2 Set the embedding orders of the chat tiers to 2 and 3, and move `devops-background` to `ollama-64gib-standard`. Update `src/devops_cli/k8s/gpu_matrix.json` and the tests that pin the topology.
  Verification: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_k8s_gpu_matrix.py tests/invariants/test_k8s_manifests.py tests/commands/k8s/test_k8s_monitoring_integration.py`

## 3. Documents (documents)

- [x] 3.1 Update `k8s/README.md`, `k8s/llm/profiles/README.md` and the Ollama knowledge base, and regenerate the documentation with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, Argo CD replaces `ollama-48gib-slow` with the two new DaemonSets. Confirm that both pods are Ready, each with one GPU (`kubectl -n llm exec ds/ollama-24gib-embed-gpu0 -c ollama -- nvidia-smi -L`).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
