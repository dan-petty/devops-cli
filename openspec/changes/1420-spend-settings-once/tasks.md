# Tasks

## 1. One priced request loads the settings at most once

- [x] Add a failing test: with a profile hook that counts `load_settings` calls, one request through `track_request_spend` loads the settings at most once for a hosted provider, a gateway call that a hosted backend served, a gateway call with no server and two hosted servers, and not at all for a local provider
  - Verification: `uv run devops ci test tests/test_ai_spend_pricing.py`
- [x] Load the settings once for each call of `is_local` with `_SettingsOnce`, pass it to the locality helpers, and give `_is_configured_cluster_host` and `_is_configured_ai_server_host` the loaded settings
  - Verification: `uv run devops ci test tests/test_ai_spend_pricing.py tests/test_ai_spend_ledger.py tests/test_validation.py`
- [x] Lower the swallowed-failures ceiling of `pricing.py` to the count that stays
  - Verification: `uv run devops ci test tests/test_swallowed_failures_ratchet.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1420-spend-settings-once`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
