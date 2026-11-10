# Tasks

## 1. Behavior

- [x] 1.1 Widen the two tests for the form `tag@sha256:digest`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py tests/core/test_renovate_config.py`
- [x] 1.2 Bump every Ollama image to `0.40.16@sha256:910d0d81…`
  - Verification: `$ grep -rc "ollama/ollama:0.40.12" k8s`

## 2. Documents

- [x] 2.1 Check that no document names the old pin
  - Verification: `$ grep -rn "ollama/ollama:0.40.12" . --exclude-dir=.git --exclude-dir=archive`
