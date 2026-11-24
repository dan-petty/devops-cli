# Proposal: #6948

## Why
When `devops_cli` is installed as a package in a container image, such as `/app/.venv` in `devops-cli-service:local`, `Path(__file__).resolve().parents[3]` points to the Python installation directory instead of the repository root. `load_cluster_secrets_table()` fails to find `tests/fixtures/cluster-secrets.toml` and returns an incomplete cluster secrets table, causing Service Image Tests to fail.

## What Changes
- Add repository fixture fallback to `EnvironmentTree.cluster_secrets` in `src/devops_cli/k8s/environment.py`.
- Add dynamic fixture discovery in `src/devops_cli/k8s/cluster_secrets.py` that inspects the repository root of `Path.cwd()` when `__file__` is in `site-packages`.
- Add test verifying `load_cluster_secrets_table()` resolves the fixture file when `__file__` resides in site-packages.

## Capabilities
- Resolve cluster secrets fixture when running from installed package environments.

## Impact
- Service Image Tests will find the cluster secrets fixture and pass across all shards.
- No breaking changes to CLI commands or external consumers.

## Feasibility
- Verified locally that monkeypatching `__file__` to `/app/.venv/...` reproduces the 10-row failure, and dynamic discovery restores all 23 rows.

## Existing Tool Considered
- Standard library `pathlib.Path` and existing `find_repository` utility.
