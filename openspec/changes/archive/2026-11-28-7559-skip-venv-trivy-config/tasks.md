# Tasks

## 1. Behavior

- [x] 1.1 Add failing unit test asserting `TrivyConfigScanner` passes `--skip-dirs` for `.venv` and `**/.venv`
  - Verification: `$ uv run devops ci test tests/security/test_trivy_config_ignore.py`
- [x] 1.2 Pass `CONST_TRIVY_CONFIG_SKIP_DIRS` in `TrivyConfigScanner.build_command`
  - Verification: `$ uv run devops ci test tests/security/test_trivy_config_ignore.py`

## 2. Configuration

- [x] 2.1 Remove the four obsolete `.venv/` Harbor entries from `.trivyignore.yaml`
  - Verification: `$ trivy config --skip-dirs .venv --skip-dirs '**/.venv' --ignorefile .trivyignore.yaml --severity HIGH,CRITICAL .`

## 3. Quality Gate

- [x] 3.1 Verify OpenSpec and static checks
  - Verification: `$ uv run devops openspec check`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`), and verify code-scanning alerts `281` and `288` close after the next `Security Scan` run on `main`.
