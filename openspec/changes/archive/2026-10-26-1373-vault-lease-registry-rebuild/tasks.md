# Tasks

## 1. Move and rebuild session lease registry

- [x] 1.1 Add failing unit tests asserting that `get_lease_registry` rebuilds when token or address changes, and `reset_lease_registry` resets the cached instance (`uv run devops ci test tests/test_secret_resolution.py`).
- [x] 1.2 Move `get_lease_registry` and `reset_lease_registry` into `src/devops_cli/security/vault_lease.py`, rebuild when credentials change, and update resetters in `tests/conftest.py` (`uv run devops ci test tests/test_secret_resolution.py`).
- [x] 1.3 Regenerate documentation (`uv run devops docs generate --sync-readme`).

## 2. Require revoke option on vault leases command

- [x] 2.1 Add failing CLI tests asserting that `devops vault leases` without `--revoke` fails with a usage error, and `--renew` is rejected (`uv run devops ci test tests/test_vault_cmd.py`).
- [x] 2.2 Update `devops vault leases` in `src/devops_cli/commands/vault.py` to require `--revoke <lease_id>`, delete `_list_leases` and `_renew_leases`, remove the `--renew` flag, and remove obsolete listing/renew tests (`uv run devops ci test tests/test_vault_cmd.py`).
- [x] 2.3 Regenerate documentation (`uv run devops docs generate --sync-readme`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
