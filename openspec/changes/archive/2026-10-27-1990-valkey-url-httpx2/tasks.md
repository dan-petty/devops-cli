# Tasks

## 1. Defensive URL conversion and regression tests

- [x] 1.1 Guard `_as_valkey_url` in `src/devops_cli/commands/k8s/networking.py` against invalid URLs and missing hostnames (`uv run devops ci test tests/test_k8s_networking.py`)
- [x] 1.2 Add unit tests for `_as_valkey_url` testing IPv4, bracketed IPv6, localhost, and invalid URL handling in `tests/test_k8s_networking.py`
- [x] 1.3 Add assertion tests verifying removal of `_has_non_default_valkey_port` and `_should_update_valkey` in `tests/test_k8s_networking.py`
- [x] 1.4 Add assertion test verifying absence of `tcp://` and `"tcp"` scheme literals in target files in `tests/test_k8s_networking.py`
- [x] 1.5 Run full test and documentation checks (`uv run devops ci test tests/test_k8s_networking.py tests/test_k8s_proxy_addressing.py && uv run devops docs generate --sync-readme`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
