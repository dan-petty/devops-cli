# Tasks

## 1. Command construction and SBOM scanner adapter

- [x] 1.1 Add failing unit tests asserting `build_trivy_sbom_cmd` formats `["trivy", "fs", "--format", "cyclonedx", ...]` and `["trivy", "fs", "--format", "spdx-json", ...]` (`uv run pytest -n 0 tests/test_sbom.py`).
- [x] 1.2 Implement `build_trivy_sbom_cmd` in `src/devops_cli/config/commands.py`, and implement `TrivySbomScanner` and `run_trivy_sbom` in `src/devops_cli/security/sbom.py`, deleting obsolete dictionary builders and `extract_workspace_components` (`uv run pytest -n 0 tests/test_sbom.py`).
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 2. CLI integration and unchanged output streaming

- [x] 2.1 Add failing CLI tests for `devops scan sbom` verifying Trivy execution argv, unaltered file and stdout output, missing binary reporting, and format validation (`uv run pytest -n 0 tests/test_sbom.py`).
- [x] 2.2 Update `scan_sbom` in `src/devops_cli/commands/scan.py` to invoke Trivy through `run_trivy_sbom`, validate formats, check binary presence, and stream output unchanged (`uv run pytest -n 0 tests/test_sbom.py`).
- [x] 2.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 3. Quality gate and acceptance criteria validation

- [x] 3.1 Verify acceptance criteria: assert `security/sbom.py` no longer builds dicts, run fail-to-pass check, and run full gate (`uv run devops ci fail-to-pass --base origin/main && uv run devops ci`).
- [x] 3.2 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
