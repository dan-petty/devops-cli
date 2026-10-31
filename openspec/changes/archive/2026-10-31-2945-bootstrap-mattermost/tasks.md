# Tasks

## 1. Dry run and CLI registration
- [x] Add failing test for `devops k8s bootstrap-mattermost` CLI registration and dry-run output in `tests/commands/test_k8s_bootstrap_mattermost.py` (`uv run pytest tests/commands/test_k8s_bootstrap_mattermost.py`).
- [x] Implement `bootstrap_mattermost` CLI command with `@dry_run_class("request-plan")` in `src/devops_cli/commands/k8s/mattermost_bootstrap.py` and register in `src/devops_cli/commands/k8s/__init__.py` (`uv run devops k8s bootstrap-mattermost --dry-run`).
- [x] Sync CLI documentation and README (`uv run devops docs generate --sync-readme`).

## 2. In-pod configuration logic and secret sync
- [x] Add failing test for in-pod Mattermost configuration (team, channels, webhooks, slash command, keyring, secret push) in `tests/commands/test_k8s_bootstrap_mattermost.py` (`uv run pytest tests/commands/test_k8s_bootstrap_mattermost.py`).
- [x] Implement `_bootstrap_mattermost_integrations` executing `mmctl --local` in `deploy/mattermost`, storing keyring secrets, and invoking `push_secrets` (`uv run pytest tests/commands/test_k8s_bootstrap_mattermost.py`).
- [x] Verify full CI test suite and quality gates (`uv run devops ci`).
