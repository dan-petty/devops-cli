# Tasks

## 1. Security Module and Pure-Function Detection

- [x] 1.1 Write failing unit tests in `tests/test_prompt_injection.py` for INJ001 (Tag block decode & emoji sequence exempt), INJ002 (Cf format characters), INJ003 (chat delimiters), INJ005 (markdown exfil link), and EGR005 (`CanaryTokenManager`), verified via `uv run devops ci test tests/test_prompt_injection.py`.
- [x] 1.2 Implement `src/devops_cli/security/prompt_injection.py` with `decode_unicode_tags`, `escape_delimiters`, `CanaryTokenManager`, `scan_injection_text`, and `scan_injection_file`, verified via `uv run devops ci test tests/test_prompt_injection.py`.

## 2. CLI Command, MCP Exposure, and Linter Configuration

- [x] 2.1 Write failing tests in `tests/test_scan_injection.py` for `devops scan injection`, covering SARIF output, suppression policy handling, `--fail-on` exit codes, and MCP tool registration, verified via `uv run devops ci test tests/test_scan_injection.py`.
- [x] 2.2 Implement `scan injection` command in `src/devops_cli/commands/scan.py`, add `scan_injection` to `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py`, and add language strings in `src/devops_cli/lang/en/help.py` and `src/devops_cli/lang/en/messages.py`, verified via `uv run devops ci test tests/test_scan_injection.py`.
- [x] 2.3 Add Ruff rules `PLE2502`, `PLE2510`, `PLE2512`, `PLE2513`, `PLE2514`, and `PLE2515` to `pyproject.toml` and verify linting with `uv run ruff check`.
- [x] 2.4 Regenerate CLI documentation and verify with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Archive the change after quality gate passes.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
