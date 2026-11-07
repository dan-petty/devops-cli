# Proposal

## Why

Issue #3748 is part 3 of 6 of #1335. Four roadmap test files hold many behaviours. A failing file does not say which behaviour broke, and each edit of one of them conflicts with the edits of the other sessions that work on the roadmap.

| File at origin/main 734e060b | Lines | Tests |
| :--- | :--- | :--- |
| `tests/roadmap/refine/test_roadmap_refine.py` | 4,360 | 231 |
| `tests/roadmap/test_roadmap_run.py` | 3,124 | 77 |
| `tests/roadmap/intake/test_roadmap_intake.py` | 2,550 | 125 |
| `tests/roadmap/stores/test_roadmap_github_store.py` | 1,729 | 123 |

Counts are test ids from `pytest --collect-only`, so a parametrized test counts once for each case. `tests/roadmap/stores/test_roadmap_store_contract.py` is one contract suite with one subject. It stays.

## What Changes

- The four files are gone. Their 556 tests move, with the same names and the same bodies, into 60 files. Each file holds one behaviour and is named by it. No new test file is longer than 511 lines.
  - `tests/roadmap/` (the tests of `roadmap/run.py`): `test_roadmap_run_due_table.py`, `_service.py`, `_checkout.py`, `_metrics.py`, `_intake_row.py`, `_github_requests.py`, `_lanes.py`, `_failure_ledger.py`, `_errors.py`, `_scoped_update.py`, `_job_rows.py`, `_job_counts.py` and `_adapter_imports.py`.
  - `tests/roadmap/refine/`: `test_roadmap_refine_` with `context`, `web_search`, `proposal`, `sanitize`, `selection`, `command`, `gateway_failures`, `failure_record`, `next_step`, `waits`, `blocked`, `item_option`, `cited_paths`, `comment_cap`, `questions`, `decisions`, `authors`, `covers_check`, `stage_return`, `person_wait` and `recorded_wait`.
  - `tests/roadmap/intake/`: `test_roadmap_intake_` with `placement`, `shortlist`, `title_labels`, `labels_file`, `duplicates`, `sub_issues`, `evidence`, `untrusted_text`, `model_reply`, `write_failures`, `agent_candidates`, `command`, `dry_run`, `mcp_mirror` and `github_requests`.
  - `tests/roadmap/stores/`: `test_roadmap_github_store_` with `milestones`, `items`, `record_writes`, `read_failures`, `paging`, `changes`, `files`, `comments`, `issue_writes`, `history` and `repository`.
- The helpers that two or more new files use leave the old files. They go to four modules of `tests/support/`: `roadmap_run.py`, `roadmap_refine.py`, `roadmap_intake.py` and `roadmap_github_store.py`. Every module of `tests/support/` is a plugin, so the shared fixtures need no `conftest.py`. A helper that one new file uses stays in that file.
- A helper that moves to `tests/support/` and that a test file imports loses its leading underscore, because a test file must not import a private name. Thirteen of them also get a new name, because the short name is already in use in the module. In the run tests `_candidates` becomes `make_candidates`, `_clone_head` `head_of_clone`, `_commit_file` `commit_to_bare`, `_delivery` `webhook_delivery`, `_git` `git_in`, `_labeled` `labeled_changes`, `_lane` `lane_table`, `_make_bare_remote` `bare_remote`, `_schedule` `read_schedule` and `_stamp` `stamp_successes`. In the refine tests `_TOOL` becomes `NO_OPEN_TOOL` and `_blocked_by` `blocked_by_issue`. In the intake tests `_labels` becomes `labels_of`. No test changes its name.
- A constant that was one tuple assignment (`FIRST, SECOND, THIRD = ...`) is one assignment for each name in the support modules, because the helper-module check of `tests/gate/tree_checks/helper_modules.py` accepts only a name as the target of an assignment.
- The constant `LABELS_YML` of the intake tests reads `.github/labels.yml` from `REPO_ROOT`, not from the working directory. Every module of `tests/support/` loads in each pytest run, also in the nested runs of `tests/config/test_isolation_tripwire.py`, whose working directory is a temporary one.
- Two syrupy snapshots follow their tests: `tests/roadmap/intake/__snapshots__/test_roadmap_intake.ambr` becomes `test_roadmap_intake_duplicates.ambr`, and `tests/roadmap/refine/__snapshots__/test_roadmap_refine.ambr` becomes `test_roadmap_refine_next_step.ambr`.
- Two helpers have no user and are deleted: the constant `COMMIT_IDENTITY` of the run tests and the constant `ISSUE_URL` of the store tests.
- The docstring of `tests/roadmap/stores/test_roadmap_store_contract.py` names the new store test files, because the old path in it was stale.
- No product code changes. The change has no spec delta, so `skip_specs: true` is set.
- The change fits one pull request.

Test count: 556 before, 556 after. No test is merged or deleted. A script compared the multiset of test names of `tests/roadmap` before and after: both are equal. A second script parsed the four old files and the 64 new files and compared each moved function, class and constant with its source after the renames above: all 640 top-level definitions match.

## Impact

- `tests/roadmap/`, `tests/roadmap/refine/`, `tests/roadmap/intake/`, `tests/roadmap/stores/` and `tests/support/roadmap_*.py`.
- No `conftest.py` changes.
- Out of scope: the `devops_cli` patches and the private imports that some moved bodies still hold. Issue #1336 bans them and owns that work. This change keeps each body unchanged, so a reviewer sees pure moves.

## Feasibility

Checked on `origin/main` 734e060b, 2026-11-07. The text of #3748 was written at 29309f04, so each claim was read again.

- The four files exist, in the subpackage folders that #3187 made. `ls tests/roadmap/refine tests/roadmap/intake tests/roadmap/stores` shows `test_roadmap_refine.py`, `test_roadmap_intake.py` and `test_roadmap_github_store.py`. `test_roadmap_run.py` stays at the top of `tests/roadmap/`, because `roadmap/run.py` is a module of the top of the package.
- Part 2 (#3746) is merged: `install_roadmap_store` is in `src/devops_cli/roadmap/stores/store.py`, and the four files use the `roadmap_store` fixture. The dependency holds.
- The counts of the issue are out of date: the files grew to 4,360, 3,124, 2,550 and 1,729 lines. The issue counted test functions. This change counts test ids, so 556.
- The claim "`git diff -M --stat` shows the moves as renames" cannot hold for a split. Git pairs a deleted file with one added file only when the two share about half of their text. Each new file holds at most a fifth of an old file. `git diff -M10% -C10% --find-copies-harder --stat` pairs only 7 of the 64 new files with an old file. The proof of the move is instead the comparison of the test names and the comparison of each moved definition with its source, both described above.
- The claim "`test_roadmap_github_store.py` may hold one behaviour only" is false: it holds eleven (milestones, item reads, record writes, read failures, paging, changes, files, comments, issue writes, history and repository facts). It is split.
- The moved tests still catch faults. I changed the product code in the work tree, ran the new files and restored the code. Four faults fail the migrated tests. `listing_path` of the GitHub roadmap store asks for one entry more than the page size (30 failures in the `paging`, `items` and `changes` store files). `sanitize_text` of `roadmap/refine/refine.py` returns its text as it is (46 failures in `test_roadmap_refine_sanitize.py`). The shortlist of `roadmap/intake/intake.py` holds one item more (1 failure in `test_roadmap_intake_shortlist.py`). `ensure_checkout` of `roadmap/run.py` drops `--force` from the checkout (4 failures in `test_roadmap_run_checkout.py`).
- The full run of `tests/roadmap` passes: 5,048 passed and 1 skipped, the same 5,049 tests as before the move.
- `tests/gate/tree_checks/helper_modules.py` allows a helper module to hold only statements that bind names. The four new support modules hold defs, classes and assignments only.

## Existing Tool Considered

`pytest --collect-only` lists the test ids before and after. `ruff check --select F401,I --fix` and `ruff format` clean the imports of each new file. Python's `ast` module cut each definition from the old file and checked the copy. No open tool groups tests by behaviour: that needs a reader who knows the glossary of `CONTEXT.md`, and the module-grouping change #3187 recorded the same. Nothing is built that stays in the repository: the scripts that cut the files are scratch files under `.data/agent/scratch/`. The change deletes four test files and two unused constants.
