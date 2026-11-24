# Proposal: #6957

## Why
In `tests/k8s/test_cluster_secrets_file.py`, `test_resolve_fixture_secrets_file_variants` tests `_resolve_fixture_secrets_file()` by asserting `assert cs._resolve_fixture_secrets_file() == cs._FIXTURE_SECRETS_FILE`. When `devops_cli` runs from site-packages (such as in `/app/.venv` inside the Service test image), `_FIXTURE_SECRETS_FILE` does not exist on disk, so `_resolve_fixture_secrets_file()` falls back to `_FALLBACK_FIXTURE_SECRETS_FILE` (`tests/fixtures/cluster-secrets.toml`). This causes `test_resolve_fixture_secrets_file_variants` to fail with `AssertionError`, breaking `Service Image Tests (shard 1 of 6)` in CI.

Additionally, `src/devops_cli/k8s/cluster_secrets.py` restricts fallback fixture loading with `if env_file is None and k8s_dir is None:`, preventing fallback when `k8s_dir` is passed without a local cluster-secrets file.

## What Changes
- Update `test_resolve_fixture_secrets_file_variants` in `tests/k8s/test_cluster_secrets_file.py` to use a monkeypatched existing path in `tmp_path` for primary resolution.
- Allow `load_cluster_secrets_table()` to fall back to `_resolve_fixture_secrets_file()` when `env_file` is `None` regardless of `k8s_dir`.
- This change alters no behavior that external consumers observe, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`.

This change fits one pull request.

## Capabilities
- Hermetic fixture resolution in `tests/k8s/test_cluster_secrets_file.py` and robust fallback in `load_cluster_secrets_table()`.

## Impact
- `Service Image Tests` pass across all shards.
- No breaking changes.

## Feasibility
- Verified with command `uv run python -c 'import devops_cli.k8s.cluster_secrets as cs; from pathlib import Path; cs._FIXTURE_SECRETS_FILE = Path("/app/.venv/lib/python3.14/tests/fixtures/cluster-secrets.toml"); assert cs._resolve_fixture_secrets_file() == cs._FIXTURE_SECRETS_FILE'` that `AssertionError` reproduces the exact CI failure.
- Verified that monkeypatching `_FIXTURE_SECRETS_FILE` to an existing temporary path makes the test pass hermetically.

## Existing Tool Considered
- Standard library `pathlib.Path` and `pytest.MonkeyPatch`. No new tool is necessary. Deletes zero internal files.
