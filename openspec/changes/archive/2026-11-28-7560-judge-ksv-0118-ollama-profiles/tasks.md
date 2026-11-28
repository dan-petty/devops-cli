# Tasks

## 1. Test Fixture Fix

- [x] 1.1 Set a non-root pod `securityContext` on `DaemonSet/ollama-16gib` in `tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml`
  - Verification: `$ trivy config --severity LOW,MEDIUM,HIGH,CRITICAL tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml`
- [x] 1.2 Verify existing Kubernetes tests using `tests/fixtures/k8s_environment` pass
  - Verification: `$ uv run pytest tests/commands/k8s/test_k8s_gpu_placement.py tests/commands/k8s/test_k8s_ollama_prune.py`

## 2. Quality Gate

- [x] 2.1 Validate OpenSpec metadata and repository static checks
  - Verification: `$ uv run devops openspec check`

Pending a person: confirm code-scanning alert 1258 closes on `main` after the `Security Scan` workflow completes.
