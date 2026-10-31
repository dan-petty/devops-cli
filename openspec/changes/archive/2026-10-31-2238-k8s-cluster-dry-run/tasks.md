# Tasks

## 1. Plan Builders and Dry-Run Implementation
- [x] 1.1 Add failing tests in `tests/commands/test_k8s_dry_run.py` verifying dry-run output and zero external calls for all 14 commands. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -n 0`.
- [x] 1.2 Create `src/devops_cli/k8s/cluster_plans.py` with pure argument builders and request planners for Kubernetes cluster operations. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -k test_plans -n 0`.
- [x] 1.3 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/security_audit.py` for `k8s audit` and `k8s rbac-audit`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -k "audit" -n 0`.
- [x] 1.4 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/cluster_context.py` for `contexts`, `status`, `switch-context`, and `logs`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -k "context or logs or status" -n 0`.
- [x] 1.5 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/diagnostics.py` for `pods`, `stream-logs`, and `security-stream`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -k "pods or stream" -n 0`.
- [x] 1.6 Wire `@dry_run_class` into `src/devops_cli/commands/k8s/gpu_matrix.py` for `gpu-matrix` as `no-external-request`. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -k "gpu_matrix" -n 0`.
- [x] 1.7 Wire `@dry_run_class` into `src/devops_cli/commands/k8s/networking.py` for `port-forward` (`request-plan`), `port-forward-status` (`no-external-request`), `port-forward-stop` (`no-external-request` with local preview), and `service-url` (`request-plan`). Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_dry_run.py -k "port_forward or service_url" -n 0`.
- [x] 1.8 Remove the 14 commands from `tests/fixtures/dry_run_gaps.json` and keep list sorted. Verification: `uv run pytest tests/invariants/test_dry_run_class_ratchet.py -n 0`.
- [x] 1.9 Regenerate command documentation with `uv run devops docs generate --sync-readme`. Verification: `git diff docs/ README.md`.
- [x] 1.10 Archive OpenSpec change folder with `uv run devops openspec archive 2238-k8s-cluster-dry-run`. Verification: `uv run devops openspec check`.

## Workflow follow-up
Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
