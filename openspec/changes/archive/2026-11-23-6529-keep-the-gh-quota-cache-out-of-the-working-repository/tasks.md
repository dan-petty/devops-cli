# Tasks

## 1. Behavior

- [x] 1.1 Write tests verifying cache root outside working repository and clean git status
  - Verification: `$ uv run pytest tests/github/test_github_rate_limiter.py -k "cache_root or rate_limit_command_writes_no_cache"`
- [x] 1.2 Update `_identity_cache_root` to resolve under `platformdirs.user_cache_dir`
  - Verification: `$ uv run pytest tests/github/test_github_rate_limiter.py`

## 2. Validation

- [x] 2.1 Verify setting overrides test suite
  - Verification: `$ uv run pytest tests/config/test_setting_overrides_reach_their_readers.py`
- [x] 2.2 Run full CI quality gate
  - Verification: `$ uv run devops ci --check`
