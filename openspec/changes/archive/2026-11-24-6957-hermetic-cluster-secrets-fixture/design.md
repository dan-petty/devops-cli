# Design

## Decisions
- Hermetically test primary, fallback, and absent resolution in `test_resolve_fixture_secrets_file_variants` by setting explicit mock paths via `monkeypatch`.
- Fall back to `_resolve_fixture_secrets_file()` when `env_file is None` in `load_cluster_secrets_table()` without requiring `k8s_dir is None`.

## Rejected alternatives
- Bundle `cluster-secrets.toml` inside the Python package: Environment manifests belong outside product package distributions.
- Hardcode `/workspace/project` in fixture resolution: Fails outside containerized test runners and violates package portability.
