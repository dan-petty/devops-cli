# Tasks

## 1. The guard refuses every key of the loader and shell families

- [x] Add failing tests: a caller override of `LD_AUDIT`, `LD_ORIGIN_PATH`, `DYLD_FRAMEWORK_PATH`, `DYLD_FALLBACK_LIBRARY_PATH`, `DYLD_FALLBACK_FRAMEWORK_PATH` or `BASH_FUNC_x%%`, in upper and lower case, raises `SecurityError`; `PATH`, `HOME`, `ENVIRONMENT`, `EXAMPLE_DYLD_FLAG` and `BASH_FUNCTIONS` reach the child
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] Add `CONST_CODE_LOADING_ENV_PATTERNS` with its sources to `config/constants.py`, match each override key against it in `build_subprocess_env`, and delete the local set `dangerous_env_keys`
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`

## 2. The rule pack test gives Semgrep only its own setting

- [x] Add a failing test: with `BASH_FUNC_which%%` and `GITHUB_TOKEN` in the environment, `run_rule_pack_tests` starts `semgrep --version` and `semgrep --test` with the caller override `SEMGREP_ENABLE_VERSION_CHECK=0` and no other key
  - Verification: `uv run devops ci test tests/test_review_rules_pack.py`
- [x] Give `semgrep --version` and `semgrep --test` only the override `SEMGREP_ENABLE_VERSION_CHECK=0`, and delete the full copy of the environment
  - Verification: `uv run devops ci test tests/test_review_rules_pack.py`

## 3. Documentation

- [x] Describe the guard in the safe subprocess execution section of `ARCHITECTURE.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2205-refuse-code-loading-env-keys`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
