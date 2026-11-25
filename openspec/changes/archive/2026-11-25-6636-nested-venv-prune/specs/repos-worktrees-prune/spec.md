## MODIFIED Requirements

### Requirement: Regenerable paths hold no data
The count of ignored data files SHALL leave out the regenerable paths: the caches and build outputs that a command makes again. They are `dist`, `build`, `htmlcov`, `.data/cache`, `.data/rag`, the coverage outputs under `.data/`, `.coverage` and `.coverage.*` at the root and under `.data/`, and each `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.hypothesis` and `node_modules` path at any depth. An empty directory holds no data file.

#### Scenario: Only caches
- **WHEN** a clean worktree under the managed folder at a merged head holds only `.venv/x`, `src/pkg/__pycache__/m.pyc` and `.pytest_cache/v`
- **THEN** `prune --confirm` removes it and reports it as removed

#### Scenario: Nested virtual environment
- **WHEN** a worktree holds ignored files only under `sub/project/.venv`
- **THEN** `count_ignored_data_files` returns 0, and `devops repos worktrees prune` without `--confirm` previews a merged worktree holding only `sub/project/.venv` as removable

#### Scenario: Data file beside a nested virtual environment
- **WHEN** a worktree holds an ignored file in `.data/agent/` and an ignored file in `sub/project/.venv`
- **THEN** `count_ignored_data_files` returns 1

#### Scenario: Nested build directory is data
- **WHEN** a worktree holds an ignored file in `sub/project/build/`
- **THEN** `count_ignored_data_files` returns 1

#### Scenario: Only the data cache
- **WHEN** a clean worktree under the managed folder at a merged head holds only `.data/cache/x`
- **THEN** `prune --confirm` removes it

#### Scenario: A note named like coverage output
- **WHEN** a worktree under the managed folder holds `.coverage`, `.coverage.host.1`, `.data/.coverage`, `.data/.coverage.host.2` and `.data/agent/notes/.coverage-notes.md`, which `.gitignore` hides
- **THEN** the scope rule refuses the worktree with the reason `holds 1 ignored data file`
