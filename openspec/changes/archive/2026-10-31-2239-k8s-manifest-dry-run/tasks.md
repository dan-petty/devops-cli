# Tasks

## 1. Plan Builders and Dry-Run Implementation
- [x] 1.1 Add failing tests in `tests/commands/test_k8s_manifest_dry_run.py` verifying dry-run output and zero external calls for all 18 commands. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -n 0`.
- [x] 1.2 Create `src/devops_cli/k8s/manifest_plans.py` with pure argument builders and request planners for Kubernetes manifest, stack, and kustomize operations. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k test_plans -n 0`.
- [x] 1.3 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/cluster_context.py` for `apply` and `render`. Expose `--dry-run` on `render`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "apply or render" -n 0`.
- [x] 1.4 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/bootstrap.py` for `bootstrap`. Delete `@dry_run_command`. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "bootstrap" -n 0`.
- [x] 1.5 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/stack_lifecycle.py` for `bootstrap-openwebui`, `sync-secrets`, and `teardown-stack`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "openwebui or sync_secrets or teardown" -n 0`.
- [x] 1.6 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/diagnostics.py` for `chaos` and `diff-helm`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "chaos or diff_helm" -n 0`.
- [x] 1.7 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/networking.py` for `configure-urls`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "configure_urls" -n 0`.
- [x] 1.8 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/tls_management.py` for `create-tls-secret` and `enable-tls`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "tls" -n 0`.
- [x] 1.9 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/k8s/security_audit.py` for `check-deprecated` and `validate`. Wire `no-external-request` for `lint` and `validate-policy`. Delete echo-only previews. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "audit or validate or lint" -n 0`.
- [x] 1.10 Wire `@dry_run_class` and request plan logic into `src/devops_cli/commands/kustomize.py` for `apply`, `build`, and `diff`. Expose `--dry-run` on `build` and `diff`. Verification: `uv run pytest tests/commands/test_k8s_manifest_dry_run.py -k "kustomize" -n 0`.
- [x] 1.11 Remove the 18 commands from `tests/fixtures/dry_run_gaps.json` and keep list sorted. Verification: `uv run pytest tests/invariants/test_dry_run_class_ratchet.py -n 0`.
- [x] 1.12 Regenerate command documentation with `uv run devops docs generate --sync-readme`. Verification: `git diff docs/ README.md`.
- [x] 1.13 Archive OpenSpec change folder with `uv run devops openspec archive 2239-k8s-manifest-dry-run`. Verification: `uv run devops openspec check`.

## Workflow follow-up
Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
