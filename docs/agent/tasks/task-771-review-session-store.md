# Task: A review session store owns where review sessions live, how they are written and who reads them (#771)

**Issue**: [#771](https://github.com/dan-petty/devops-cli/issues/771)
**Scope**: scope/review
**Feasibility**: Verified against the code at `release/v0.2.39`. With `DEVOPS_CLI_DATA_DIR` unset, `data.dir` pointing at one directory and `DEVOPS_CLI_DATA_REVIEWS_DIR` at another, the review writer's resolver returned the second and the dashboard's returned none, so `list_review_sessions()` listed no session of a review that had just run. The two resolvers share every default, so one is a strict superset of the other. `tests/test_ui_dashboard.py::test_dashboard_lists_sessions_written_where_the_reviews_directory_setting_points` fails on that commit with `[]` and passes with one resolver.

## Description

A review session's files had no owner: two functions resolved where sessions live and disagreed, `findings.json` was treated as "complete" although it is written before the rest of the session, every file was written in place, and the file names were spelled out in ten modules. The item gives the session one owner in `src/devops_cli/review/session.py` and delivers it as several pull requests, each saying `Part of #771`, the last closing the issue. This file is the one record of all of them.

## Deliverables

### PR 1: One resolver (Part of #771)

- [x] Add `ReviewSessionStore.root()` in `src/devops_cli/review/session.py`, the one resolver of the sessions directory: `$DEVOPS_CLI_DATA_DIR/reviews` when the variable is set, otherwise `data.reviews_dir`, a relative path under the review data root (`resolve_review_data_path`), resolved, refused with a `SecurityError` for a traversal sequence or a host system directory, and never created. Writing a session creates the directory, as the orchestrator, the benchmark, the corpus and the sample validation already do with `mkdir(parents=True)`.
- [x] Delete `_get_reviews_base_dir` (`src/devops_cli/ai/review/review_environment.py`) with its `runner` re-export, and the dashboard's `_reviews_root` (`src/devops_cli/ui/data_providers.py`). The dashboard now lists the sessions a review wrote under `data.reviews_dir`, and returns no sessions for a refused or missing directory or a settings value the schema refuses.
- [x] The dashboard no longer swallows a settings failure to fall back on `./.data`: `root()` lets it surface, and the dashboard answers a refused directory (a `DevOpsCLIError`), an unreadable one (an `OSError`) and a settings value the schema refuses (a `ValueError`, as `data.reviews_dir: [1, 2]` raises) with a warning and no sessions. The swallowed-failures ceiling for `src/devops_cli/ui/data_providers.py` falls from 12 to 11.
- [x] Point every caller at `ReviewSessionStore.root()`: `commands/review.py`, `ai/review/pipeline.py` (the session directory and the roots `_checked_session_dir` allows), `ai/review/exporter.py`, `ai/review/category_metrics.py` and `ai/review/runner.py`. The redundant `resolve()` calls on the root are gone, since it is resolved.
- [x] Add the `review_store` fixture to `tests/conftest.py`, built on `isolate_data_dir`, and replace the patches of `_get_reviews_base_dir` in `tests/test_review_defects.py`, `test_review_runner.py`, `test_run_store.py`, `test_review_profile.py`, `test_review_path.py`, `test_review_backend_activity.py` and `test_review_group_analysis.py`: a test that lists, searches or checks the store asks for `review_store`, and one that only lets a command write there needs no patch, since every test already has its own data directory. `test_review_pipeline.py`, `test_review_untrusted_tree.py` and `test_data_dir_worktrees.py` call `ReviewSessionStore.root()`, so `rg -n '_get_reviews_base_dir|_reviews_root' src tests` finds nothing.
- [x] Tests in `tests/test_review_session_store.py` and `tests/test_ui_dashboard.py`: the dashboard lists sessions written where `data.reviews_dir` points; `root()` follows `DEVOPS_CLI_DATA_DIR`, a relative value under the review data root, `DEVOPS_CLI_DATA_REVIEWS_DIR` and the config file; `root()` creates nothing; a traversal sequence or `/etc` raises a `SecurityError` with its exit code and error code, and the dashboard lists no session for either or for a `data.reviews_dir` that is not a path.

### Remaining parts of #771

- Atomic session writes and the completion marker: `ReviewSession` with its writers, `complete.json` written after `profile.json`, listing and `latest()` using the marker, and `analysis.json` written through the store. Follows in #771.
- Every reader and writer through the store: history, the exporter, `review stats`, `review findings`, `review verify`, `review score`, the corpus commands, `_find_session_dir`, the dashboard summary and adjudication, with the invariant that no module outside the store names a session file. Follows in #771.
- The rename of `candidates.json` to `raised_findings.json` and of `--candidates` and `--candidate` to `--raised`, with the changelog fragment and the generated CLI docs. Follows in #771.
