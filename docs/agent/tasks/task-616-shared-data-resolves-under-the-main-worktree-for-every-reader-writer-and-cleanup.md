# Task 616: Shared Data Resolves Under the Main Worktree for Every Reader, Writer and Cleanup

**Issue**: [#616](https://github.com/dan-petty/devops-cli/issues/616)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/config`, `priority/p1-high`

---

## 1. Description & Objectives

#553 established that shared data (reviews, benchmarks, feedback datasets, caches, model bundles, incident logs, registries, and hallucination catalogues) must resolve under the **main** worktree through `resolve_data_path`, so linked and nested worktrees share one data directory (`.data`), removing a worktree loses no data, and commands run identically from any worktree.

However, several readers, writers, and cleanup routines still anchored data to the top-most parent holding `.git` or `pyproject.toml` (via `find_top_level_repo_root()`) or to `Path.cwd()`:
- `devops workspace clean` / `cleanup_data_tier`: pruned `<top>/.data` and ignored `data.dir` / `DEVOPS_CLI_DATA_DIR`; from an outside worktree, it pruned nothing.
- Hallucination catalogue: relative `DEVOPS_CLI_DATA_DIR` was anchored to top-most root instead of `main_worktree_root`.
- `devops benchmark --suite` and `devops ai prompt-eval`: looked for feedback datasets under the worktree root; the benchmark fell back silently to baseline cases, and prompt-eval evaluated against the wrong directory.
- Model bundles: `devops ai bundle-models` placed relative `--output-dir` under the top-most root.
- Workspace discovery (`GET /workspace`): scanned `<root>/repos`, which exists only in the main checkout, listing nothing from outside worktrees.
- Other data sites: CI cache, analysis cache, library drift auditor, UI data providers, controller data dir, sandbox registry and logs, GitHub rate limiter quota cache, GitHub GraphQL cache, spend pricing registry, Argo gitops cache, audit logger, and port forward daemon used local paths or top-most roots without routing through `resolve_data_path`.

### Key Deliverables Completed:

- [x] **Workspace Cleanup Alignment & Guardrails** (`src/devops_cli/core/cleanup.py`, `src/devops_cli/commands/workspace.py`):
  - Updated `cleanup_data_tier` to resolve the data directory via `resolve_data_path()` anchored to `main_worktree_root()`.
  - Added strict `_is_dedicated_data_dir()` pre-flight guardrail refusing to prune if `data_dir` equals `main_root`, `repo_root`, filesystem root `/`, home directory, or is not named `.data` / `data` or a descendant of `main_root`.
  - Updated `_prune_single_item()` to evaluate relative paths against `main_root` and prune cleanly from any worktree.
- [x] **Hallucination Catalogue & Benchmarks** (`src/devops_cli/ai/review/common_hallucinations.py`, `src/devops_cli/ai/benchmark/suite.py`, `src/devops_cli/ai/prompt_eval.py`):
  - Updated `get_common_hallucinations_file_path()` to resolve relative `DEVOPS_CLI_DATA_DIR` and default catalog paths via `resolve_data_path()`.
  - Updated benchmark suite dataset resolution (`_resolve_suite_dataset_path()`) to resolve datasets via `resolve_data_path(ds)` with `main_worktree_root()` included in `allowed_roots`.
  - Separated shared dataset loading from source evaluation in `prompt_eval.py`: `_resolve_dataset_path()` resolves against `main_worktree_root()`, while code under test remains anchored to the active worktree root.
- [x] **Model Bundling & Server Workspaces** (`src/devops_cli/ai/model_bundler.py`, `src/devops_cli/server/routes/workspace.py`):
  - Updated `bundle_ollama_models()` to resolve `models_dir` and relative `output_dir` via `resolve_data_path()`.
  - Updated `list_workspaces()` to search `main_worktree_root() / "repos"`, discovering repositories correctly from outside worktrees.
- [x] **Caches, Registries & Incident Logs Alignment**:
  - `src/devops_cli/ci/cache.py`: `resolve_ci_cache_path()` routes `settings.data.cache_dir` through `resolve_data_path()`.
  - `src/devops_cli/ai/analyze/cache.py` & `src/devops_cli/commands/analyze.py`: eliminated redundant top-level lookups, routing through `resolve_data_path()`.
  - `src/devops_cli/ai/library/drift_auditor.py` & `src/devops_cli/commands/ai_ingest.py`: `contracts_dir` resolved via `resolve_data_path()`.
  - `src/devops_cli/commands/ai.py`: `audit_library_usage_cmd` default report path resolves via `resolve_data_path()`.
  - `src/devops_cli/ui/data_providers.py`: `_reviews_root()` resolves via `resolve_data_path()`.
  - `src/devops_cli/ai/controller/manager.py`: `_resolve_data_dir()` resolves relative paths via `resolve_data_path()`.
  - `src/devops_cli/sandbox/registry.py` & `src/devops_cli/sandbox/logs.py`: registry and incident paths resolve via `resolve_data_path()`.
  - `src/devops_cli/github/rate_limiter.py` & `src/devops_cli/github/graphql.py`: quota cache and GraphQL cache resolve via `resolve_data_path()`.
  - `src/devops_cli/ai/spend/pricing.py`: pricing registry data dir resolves via `resolve_data_path()`.
  - `src/devops_cli/argo/gitops.py`: Argo baseline cache resolves via `resolve_data_path()`.
  - `src/devops_cli/core/audit.py`: audit log verification allowed roots include `resolve_data_path()`.
  - `src/devops_cli/k8s/port_forward_daemon.py`: state file resolves via `resolve_data_path()`.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_data_dir_worktrees.py`: added comprehensive test suite testing outside worktrees, nested worktrees, custom `data.dir` / `DEVOPS_CLI_DATA_DIR`, `devops workspace clean` pruning, cleanup refusal guardrails on repo roots, and prompt-eval source-vs-data separation.
  - All tests passing with structural tuple equality assertions and zero cyclomatic complexity regressions.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
