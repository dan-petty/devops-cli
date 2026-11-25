# Tasks

## 1. Failing tests

- [ ] Add failing unit tests in `tests/test_cloudflare_commands.py` covering multi-page access applications, multi-page access policies, 429 retries with `Retry-After`, and non-retried 403 errors
  - Verification: `uv run devops ci test tests/test_cloudflare_commands.py`

## 2. Fix

- [ ] Implement paginated GET helper `_get_paginated` in `src/devops_cli/cloudflare/client.py` and update `list_dns_records`, `list_access_applications`, and `get_access_policies`
  - Verification: `uv run devops ci test tests/test_cloudflare_commands.py`
- [ ] Implement tenacity-based retry with `Retry-After` support in `src/devops_cli/cloudflare/client.py`
  - Verification: `uv run devops ci test tests/test_cloudflare_commands.py`

## 3. Verification and static checks

- [ ] Verify fail-to-pass check run passes against base
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] Verify full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
