# Design

## Decisions
- Update `EnvironmentTree.cluster_secrets` to fall back to `self.repo / "tests" / "fixtures" / "cluster-secrets.toml"` when the environment root lacks `cluster-secrets.toml`.
- Update `cluster_secrets.py` to check repository candidates via `find_repository(Path.cwd())` and `Path.cwd()` if `__file__.parents[3]` is not a repository root.

## Rejected alternatives
- Bundle `cluster-secrets.toml` inside Python package: Environment manifests belong outside product package distributions.
- Hardcode `/workspace/project` in code: Fails outside containerized test runners.
