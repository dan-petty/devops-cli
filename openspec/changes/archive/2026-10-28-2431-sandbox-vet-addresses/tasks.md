# Tasks

## 1. The metrics scrape

- [x] Add the row of the metrics scrape (loopback) to `test_each_caller_dials_at_its_level`, with and without `ai.allow_private_network`, and add `test_a_scrape_looks_up_its_host_once`
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_sandbox_metrics.py`
- [x] Delete the pre-flight `validate_url_egress` call of `_validate_scrape_url` and its loopback shortcut, and keep the scheme and host check
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_sandbox_metrics.py`

## 2. The whitelist NetworkPolicy

- [x] Add `test_the_whitelist_policy_looks_up_each_name_once`, `test_the_whitelist_policy_refuses_an_answer_outside_its_level`, `test_a_whitelist_name_that_does_not_resolve_is_refused` and `test_network_policy_exits_1_naming_a_whitelist_name_whose_answer_it_refuses`
  - Verification: `uv run devops ci test tests/test_sandbox_networking.py`
- [x] Resolve each whitelist name with `vet_addresses` at the port of its entry: the public level in `_resolve_public_dns`, the private level and then the private-or-loopback rule in `_resolve_local_dns`. Delete the two `socket.getaddrinfo` calls and their classification of the answers. Name the time-of-check gap in each docstring, and raise `SandboxValidationError` for each refusal of the builders
  - Verification: `uv run devops ci test tests/test_sandbox_networking.py tests/test_sandbox_policy_properties.py tests/test_validation.py`
- [x] Make the public whitelist validator call `is_loopback_or_private_host` with `resolve_dns=False`
  - Verification: `uv run devops ci test tests/test_sandbox_networking.py tests/test_sandbox_policy_properties.py`

## 3. Documentation

- [x] Name the sandbox metrics scrape among the factory clients in `README.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2431-sandbox-vet-addresses`

## Workflow follow-up

- Part 5 (#2437) deletes `_resolve_host_ips` and `_enforce_non_private_ssrf`, changes the check of the container engine endpoint in `tests/test_sandbox_lifecycle.py`, and writes the general statement that every HTTP client is checked at the connect.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
