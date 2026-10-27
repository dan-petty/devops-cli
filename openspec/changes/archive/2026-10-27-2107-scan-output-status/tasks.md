# Tasks

## 1. Scanner JSON and YAML output includes status and reason

- [x] 1.1 Write failing tests in `tests/test_scan.py` and update `tests/test_security_semgrep.py` asserting that `devops scan trivy|secrets|sast|iac` with `--json` or `--format yaml` returns a mapping with `status`, `reason`, and `findings`. Verify that `uv run devops ci test tests/test_scan.py tests/test_security_semgrep.py` fails on the base.
- [x] 1.2 Update `scan_trivy`, `scan_secrets`, `scan_sast`, and `scan_iac` in `src/devops_cli/commands/scan.py` to serialize `status`, `reason`, and `findings` for non-table formats, and verify that `uv run devops ci test tests/test_scan.py tests/test_security_semgrep.py tests/test_security_gitleaks.py` passes.
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme` and verify that `uv run devops docs check` and `uv run devops openspec check` pass.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
