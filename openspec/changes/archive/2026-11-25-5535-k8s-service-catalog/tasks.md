# Tasks

## 1. Behavior

- [x] 1.1 Write failing offline fixture tests covering `devops k8s catalog` Markdown output, `fnmatch` globs, operator workloads (`Cluster`, `Mattermost`), backend-Service UI resolution and sorting, duplicate/unclaimed/missing/unknown failures, `--check`, `--format json`, and zero-subprocess `--dry-run`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_catalog.py`
- [x] 1.2 Expose public `application_renders`, add `src/devops_cli/k8s/catalog.py` and `CatalogError`, and wire `devops k8s catalog` in `src/devops_cli/commands/k8s/`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_catalog.py`

## 2. Documents

- [x] 2.1 Regenerate CLI documentation and MCP snapshot listing `devops k8s catalog` and run docs validation
  - Verification: `$ uv run devops ci docs`
