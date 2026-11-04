# Tasks

## 1. Set one CPU thread on an embedding-only tier (behavior)

- [x] 1.1 Change the tests of the rendered tiers, so they ask for `LLAMA_ARG_THREADS` on an embedding-only tier and not on a chat tier.
  Verification: `uv run devops ci test tests/k8s/test_gpu_thresholds.py`
- [x] 1.2 Set the variable in `src/devops_cli/k8s/gpu_thresholds.py`, and run `uv run devops ai gateway render --apply`.
  Verification: `uv run devops ai gateway render`

## 2. Documents (documents)

- [x] 2.1 Give the measured numbers and the reason for `simple-shuffle` in `k8s/llm/gateway/config.yaml`, `k8s/llm/profiles/ollama-profiles.yaml`, `k8s/README.md` and the Ollama knowledge base.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, confirm that both pods are Ready, and that `kubectl top pod -n llm` shows about 1 core for each instance under load.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
