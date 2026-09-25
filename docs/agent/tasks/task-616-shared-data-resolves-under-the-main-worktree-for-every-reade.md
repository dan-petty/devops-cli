# Task 616: Shared Data Resolves Under the Main Worktree for Every Reader, Writer and Cleanup

**Issue**: [#616](https://github.com/dan-petty/devops-cli/issues/616)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/config`, `priority/p1-high`

---

## 1. Description & Objectives

#553 made shared data resolve under the main worktree through `resolve_data_path`, so every
worktree shares one data directory. Several sites still anchored data at the top-most parent
holding `.git` or `pyproject.toml`, or at the current directory. From a linked worktree created
outside the checkout they read and wrote `<worktree>/.data`, so data split across worktrees and
was lost when one was removed:
- `devops workspace clean` pruned `<top>/.data`, ignoring `data.dir` and `DEVOPS_CLI_DATA_DIR`;
- the hallucination catalogue anchored a relative `DEVOPS_CLI_DATA_DIR` at the top-most root;
- `devops benchmark --suite` and `devops ai prompt-eval` looked for the feedback dataset under
  the worktree; the benchmark then silently fell back to its baseline cases;
- `devops ai bundle-models` put a relative `--output-dir` under the top-most root;
- workspace discovery scanned `<root>/repos`, which exists only in the main checkout;
- the analysis cache, the CI result cache, the library drift report, the dashboard's data
  providers, the controller and the sandbox logs and registry used the current directory.

### Key Deliverables Completed:

- [x] **One resolver for every data site**: each of the sites above resolves through
  `resolve_data_path`, so the main checkout and every worktree share one data directory.
  `prompt-eval` reads its dataset from shared data and verifies sources in the worktree it runs
  in. A relative `--dataset` or `--output-dir` is under the main worktree, as the help now says.
  Workspace discovery lists the main checkout's `repos/`.
- [x] **CI result cache per worktree in the shared cache**: the cache file lives in
  `data.cache_dir`, named after the worktree's root, so a gate never trusts a result recorded
  for another worktree's files and parallel worktrees do not evict each other's entries.
- [x] **`devops workspace clean` prunes where data is written, and nothing else**
  (`core/cleanup.py`):
  - it prunes the configured data directory (`data.dir`, `DEVOPS_CLI_DATA_DIR`), reports what it
    prunes relative to it, and names the directory it will prune;
  - it refuses a data directory that is a system or top-level directory, the home directory or
    a parent of it, a repository or git directory (a bare one included), a worktree of the
    repository or a parent of one, a directory holding git-tracked files or another
    repository, or another workspace's data directory, also through a symlink;
  - a child directory configured on its own, such as `data.reviews_dir`, is left alone.
- [x] **Known limit, shared with #612**: a checkout or worktree below another directory holding
  `.git` or `pyproject.toml` resolves shared data to that outer directory, as it has since
  before #585. Strict `xfail` tests record it, and it is tracked as #617.
- [x] **Automated Tests & Quality Gates** (`tests/test_data_dir_worktrees.py`,
  `tests/test_workspace_cleanup.py`, `tests/test_ci_cache.py`, `tests/test_server.py`), against
  real repositories with a linked worktree outside the checkout:
  - every data site, run from the outside worktree, resolves to the main worktree's data
    directory, and from the main checkout as before;
  - cleanup prunes the shared data from any worktree, a clone under `repos/` and a submodule,
    and refuses each unsafe directory above; its dry run names and checks what it would prune;
  - the CI cache is kept in the shared cache directory, per worktree.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
