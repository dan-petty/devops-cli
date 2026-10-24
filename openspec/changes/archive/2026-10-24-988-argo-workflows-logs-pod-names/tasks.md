# Tasks

## 1. Pod name resolution and container selection

- [x] Add failing tests for Argo Workflows v1/v2 pod naming, skipped node exclusion, `--container` option, and 404 fallback (`uv run devops ci test tests/test_argo.py tests/test_argo_crd.py`).
- [x] Implement FNV-32a hashing and v1/v2 pod name derivation with skipped node exclusion in `src/devops_cli/argo/crd.py` (`uv run devops ci test tests/test_argo_crd.py`).
- [x] Add `--container` option and 404 v2-to-v1 fallback to `workflows_logs` in `src/devops_cli/commands/argo.py` (`uv run devops ci test tests/test_argo.py`).
- [x] Add help string for `--container` in `src/devops_cli/lang/en/help.py` and regenerate documentation (`uv run devops docs generate --sync-readme`).

## 2. Verification and quality gate

- [x] Verify test suite and coverage across modified modules (`uv run devops ci test tests/test_argo.py tests/test_argo_crd.py`).
- [x] Pass the full static checks and CI gate (`uv run devops ci`).

Pending a person: On the homelab cluster, run `devops argo workflows logs <workflow>` on a finished workflow and confirm it prints the main container log.
Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
