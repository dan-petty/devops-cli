# Tasks

## 1. Exit-code gate for k8s lint

- [x] 1.1 Write `test_k8s_lint_exit_codes` in `tests/test_k8s.py` asserting exit 0 on a clean run, exit 1 with no pass line on findings and on an unavailable Kube-linter, verified to fail on `origin/main` via `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Update `test_k8s_security_tools_and_scans` in `tests/test_k8s.py` to return a `ScanOutcome` and expect exit 1 for findings, verified via `uv run devops ci test tests/test_k8s.py`
- [x] 1.3 Add `kube_linter_not_run` to `K8sMessages` in `src/devops_cli/lang/en/messages.py` and make `k8s_lint` in `src/devops_cli/commands/k8s/security_audit.py` exit 1 when the scan status is not `ran` and exit 1 after printing findings, verified via `uv run devops ci test tests/test_k8s.py`
- [x] 1.4 Regenerate the CLI reference with `uv run devops docs generate --sync-readme` and verify with `uv run devops docs check`
- [x] 1.5 Run the full gate with `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
