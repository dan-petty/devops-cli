# Task: The durable-run store resolves under the data directory (#1036)

**Issue**: [#1036](https://github.com/dan-petty/devops-cli/issues/1036)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/ai, scope/k8s

## Description
The durable-run store path (`durable_runs.db`), Kubernetes port-forward daemon state file (`k8s/port_forwards.json`), and docs ingestion directories previously resolved relative to the current working directory via direct `Path(".data/...")` construction or un-routed paths. When commands or tests ran from subdirectories or secondary worktrees, files were created locally rather than in the shared data directory or isolated test data root.

- Added `resolve_store_path(name, explicit=None, start_path=None) -> Path` in `src/devops_cli/core/repo.py` to route store paths through `resolve_data_path(data.dir / name)` while honouring explicit or absolute paths.
- Migrated `SqliteStepStore` in `src/devops_cli/ai/durable.py` to resolve through `resolve_store_path`.
- Migrated `PortForwardDaemonManager` in `src/devops_cli/k8s/port_forward_daemon.py` to resolve default state file through `resolve_store_path`.
- Migrated `DocsIngester` in `src/devops_cli/ai/library/docs_ingester.py` and mitigations cache in `src/devops_cli/ai/review/mitigations.py` to route through `resolve_store_path`.
- Added structural AST invariant tests (`test_no_direct_data_dir_path_construction_in_src` and detector verification) in `tests/test_architectural_invariants.py` preventing direct `.data` path construction in `src/` outside `config/defaults.py`.
- Added unit tests for isolated store path resolution and subdirectory state persistence in `tests/test_pydantic_ai_durable.py` and `tests/test_k8s_port_forward_daemon.py`.

## Acceptance Criteria
- [x] One helper resolves a store's default path: `data.dir` joined with the store's name, then `resolve_data_path`. The durable store, the port-forward state file and the docs-ingest directory use it. A path passed explicitly (`state_file=`, `output_dir=`, an absolute configured path) is used as given.
- [x] The durable-run store path resolves under the data directory (`resolve_data_path`, so `DEVOPS_CLI_DATA_DIR` and `data.dir` move it), unless the configured path is absolute.
- [x] An invariant test fails on any `Path` built from a `.data` literal or from `DEFAULT_DATA_DIR` in `src/` outside `config/defaults.py` that does not go through the helper. It finds nothing after this change.
- [x] From #810: the test suite leaves no `.data/k8s/port_forwards.json` in the checkout.
- [x] From #810: a forward record saved with the working directory at the repo root is listed by a manager constructed with the working directory in a subdirectory.
- [x] From #810: the symlink guard (`port_forward_daemon.py:139`, `:155`) still refuses a symlinked state file. How forwards start and stop does not change.
- [x] Tests spawn no kubectl and touch no network.
- [x] A test with `DEVOPS_CLI_DATA_DIR` set to a tmp directory asserts the store opens under it and nothing is created in the working directory.
- [x] After `uv run pytest -p no:cacheprovider -q -n 6 tests`, `git status --porcelain --ignored .data/durable_runs.db` in the checkout shows nothing new.
- [x] `changelog.d/1036.md` records the fix under `### Fixed`. `CHANGELOG.md` is not edited.
- [x] `uv run devops ci` passes.

## Deliverables
- [x] `src/devops_cli/core/repo.py`: added `resolve_store_path` helper.
- [x] `src/devops_cli/core/__init__.py`: exported `resolve_store_path`.
- [x] `src/devops_cli/ai/durable.py`: updated store path resolution.
- [x] `src/devops_cli/k8s/port_forward_daemon.py`: updated default state file resolution.
- [x] `src/devops_cli/ai/library/docs_ingester.py`: updated default target directory resolution.
- [x] `src/devops_cli/ai/review/mitigations.py`: updated mitigations directory resolution.
- [x] `tests/test_architectural_invariants.py`: AST invariant forbidding direct `.data` path construction in `src/`.
- [x] `tests/test_pydantic_ai_durable.py`: durable store data directory isolation tests.
- [x] `tests/test_k8s_port_forward_daemon.py`: default state file and subdirectory listing tests.
- [x] `changelog.d/1036.md`: changelog entry under `### Fixed`.
