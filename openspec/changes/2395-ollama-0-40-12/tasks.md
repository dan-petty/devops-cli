# Tasks

## 1. Every Ollama tier runs 0.40.12

- [x] 1.1 Write the failing test `test_every_ollama_tier_runs_one_release_that_serves_multimodal_embedding_models` in `tests/invariants/test_k8s_manifests.py`, and see it fail on 0.34.4 with `uv run devops ci test tests/invariants/test_k8s_manifests.py`
- [x] 1.2 Set the image of each `ollama` container and each `own-model-directory` init container in `k8s/llm/profiles/ollama-profiles.yaml` to `ollama/ollama:0.40.12`; verify with `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/test_k8s.py tests/test_k8s_gpu_matrix.py`, and with `uv run devops k8s lint k8s/llm/profiles`, which gives the same findings as on `main`
- [ ] 1.3 Set `applies_to` to `tool:ollama@0.40.*` and `reviewed` to 2026-10-28 in `src/devops_cli/ai/knowledge_base/it_domains/tools/ollama.md`, and name the 0.40.12 scheduler as the source of the keep-alive rule; verify with `uv run devops ci test tests/test_kb.py tests/test_kb_manuals_metadata.py`
- [ ] 1.4 Regenerate the documentation; no command, option or message changes, so nothing changes; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- #2396 makes every tier that serves the embedding model use one KV cache type. This change does not do it, because the fix changes the KV memory of the chat model of `ollama-16gib`.
- Pending a person: after the merge, Argo CD rolls out the nine Ollama DaemonSets. Confirm that each tier with a node has a Ready pod, that `kubectl -n llm exec ds/<tier> -c ollama -- ollama --version` prints 0.40.12, and that `devops ai gateway status` shows each Ollama backend as healthy.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
