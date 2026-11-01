# Proposal

## Why

Issue #2162 names 18 review and scanner test files that cover no source line that another file does not also cover. Line coverage cannot show that a file adds no check, because a file can run a line and still assert something no other file asserts. A mutation run can show it: a file that kills no mutant that the rest of the suite leaves alive adds no check. The change measures each file this way and removes the files that add nothing.

## What Changes

- Measure, for each of the 17 files that still exist, the mutants it kills with the whole suite and the mutants that survive when the file is left out. The method is in `design.md`.
- Write the numbers in `mutation-report.md` in this change folder. Archive keeps the folder, so the record stays.
- Delete each file that has no mutant of its own. If the line coverage falls, move the tests that cover the lost lines into the file that covers the same lines.
- The change fits one pull request. It runs in ten groups. Nine groups measure files, and each needs at most a few mutation runs of at most 14400 s (4 hours) each. The last group checks the whole result.
- The change has no spec delta and sets `skip_specs: true`. It changes tests only. No `devops` command, option or message, no manifest and no service behavior changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` (new).
- Tests that the change may delete: `tests/ai/review/test_cited_code.py`, `tests/commands/test_review.py`, `tests/commands/test_review_removed_options.py`, `tests/ai/personas/test_custom_personas.py`, `tests/ai/test_review_advisory_backing.py`, `tests/ai/review/test_review_deduplication.py`, `tests/ai/review/test_review_defects_comments.py`, `tests/ai/review/test_review_defenses_and_verification.py`, `tests/ai/review/test_review_history.py`, `tests/ai/test_review_location_paths.py`, `tests/ai/test_review_loop_hardening.py`, `tests/ai/review/test_review_regression_harness.py`, `tests/ai/review/test_review_taxonomy_and_severity.py`, `tests/ai/test_review_verification.py`, `tests/ai/test_structural_positional_oracles.py`, `tests/security/test_security_kubelinter.py`, `tests/security/test_sarif_fuzzing.py`.
- Tests that may receive a moved case: the covering files named in `design.md`.

## Acceptance

- Criterion 1 (the pull request gives, for each file, the mutants it killed with the whole suite and the mutants that survive without it): groups 1 to 9. Each group writes the rows of its files in `mutation-report.md`.
- Criterion 2 (a file with no mutant of its own is deleted or its distinct case moves; line coverage and `fail_under` stay or rise): groups 1 to 9 delete the files. Group 10 compares the line coverage with the base value that group 1 records, and moves tests if it fell.
- Criterion 3 (no contract suite, invariant test or test of a security guard is deleted): the Method in `design.md` exempts these files, and each group checks the deleted set. Group 10 checks the whole deleted set.
- Criterion 4 (`uv run devops ci` passes and `Tests & Coverage` takes no longer): group 10 runs `uv run devops ci`. The duration compare needs the check runs of the pull request: pending a person (the bullet under Workflow follow-up).
- The table of the issue lists 18 files. `tests/test_security_tflint.py` is gone from `main` (see Feasibility), so 17 files remain.

## Existing code

- The mutation command is `devops ci mutate` (`src/devops_cli/ci/mutate.py`, the `mutate` command in `src/devops_cli/commands/ci.py`). Its `uv run mutmut` calls and the `[tool.mutmut]` table in `pyproject.toml` stay as they are. The change adds no code.
- Pin tests that name these files: none. `git grep` over `src`, `tests`, `docs` and the root documents finds the names only in `tests/fixtures/review_labels/` (recorded review data, not a path the tests read) and in `docs/agent/archive/historical-phases-1-to-50.md` (history).
- The tests of `devops ci mutate` (`tests/ci/test_ci_mutate.py`) and the invariant `tests/invariants/test_change_folders.py` must keep passing. The change edits neither.
- Plan #2167 (`openspec/changes/2167-the-49-test-files-that-no/`) also edits `tests/ai/review/test_cited_code.py` and `tests/commands/test_review_removed_options.py`. Whichever change merges second drops a file that the first deleted from its own list. The two changes do not conflict on any other file.
- Issue #1328 owns the move of the `ai/review` tests onto fakes. A file that this change deletes leaves that work.

## Feasibility

Checked on 2026-11-01 against `origin/main` at `4734035c`.

- The files. `git ls-files` finds 17 of the 18 files of the issue table. Four are at the path of the table: `tests/ai/review/test_cited_code.py`, `tests/commands/test_review.py`, `tests/commands/test_review_removed_options.py` and `tests/security/test_sarif_fuzzing.py`. Thirteen moved in `513bb31f` (#2830, rename at 100% similarity) and are at the paths in Impact. The test count of each file equals the count in the table (`grep -cE '^\s*(async )?def test_'`).
- One file is gone. `git log --diff-filter=D -- tests/test_security_tflint.py` shows `dbfbb653` (#2566, 2026-10-28), which also deleted `tests/test_tflint.py`. Its three tests checked a fallback CIDR scan and a mocked binary. `tests/security/test_tflint.py` now holds nine tests of the recorded tflint run and is not in the audit table. So that row is done by newer work and the plan does not list it.
- Covering files. The covering files of the issue moved too: `tests/review/test_review_group_analysis.py`, `tests/commands/test_review_adjudication.py`, `tests/ai/review/test_review_pipeline.py`, `tests/security/test_review_tool_runs.py`, `tests/ai/test_review_finding_losses.py`, `tests/ai/review/test_review_runner.py` and `tests/security/test_security_kubeconform.py` exist. `tests/test_security_sarif.py` was split in `dbfbb653` into `tests/security/test_sarif_emission.py` and `tests/security/test_sarif_ingestion.py`.
- Nothing newer deleted a file. `git log --since=2026-10-24 --diff-filter=D --name-only -- tests` names none of the 17 files.
- The overlap numbers of the issue are stale. They come from a run at `f4d7066b`, before the move of the test tree, and their data file is gitignored. The change does not use them. It measures with mutation.
- The tool. `uv run devops ci mutate --help` says: "The first run copies the whole source tree into mutants/, mutates it and runs the test suite once, serially, which can take hours; later runs reuse mutants/ and its test stats." `DEFAULT_CI_MUTATE_TIMEOUT_SECONDS` in `src/devops_cli/config/defaults.py` is `14400.0`. `uv run pytest --collect-only -q -n 0` reports `15756/15801 tests collected`. `uv run devops ci mutate --dry-run src/devops_cli/ai/personas/__init__.py` prints the `mutmut run` globs in this worktree and makes no request.
- The size of the work. I ran each of the 17 files alone with `uv run pytest <file> -n 0 --cov=devops_cli --cov-report=json:...` and counted the functions with an executed line. The 17 files run 718 functions (4720 statements) in 118 modules. 114 functions (298 statements) are run by all 17 files. The other 604 functions (4422 statements) sit in 79 modules. One run of those functions fits the timeout of one command only if it is split by group, so the plan runs the files in nine groups of measure. Per file: `test_custom_personas` runs 3 functions in 1 module, the four schema files run 48 functions in 3 modules, and `test_review_history` runs 307 functions in 44 modules.
- The mechanism. `mutmut` 3.8.0 does not say which test killed a mutant: `.venv/lib/python3.14/site-packages/mutmut/__main__.py`, function `_run`, holds the comment "TODO: we should be able to get information on which tests killed mutants". The method of the issue (a run with the file and a run without it) is therefore needed. `mutants/mutmut-stats.json` holds `tests_by_mangled_function_name`, the tests that run each function. `mutmut run <mutant>` runs an explicitly named mutant again ("Rerun mutant if it's explicitly mentioned"). `pytest.main` reads `PYTEST_ADDOPTS`: `PYTEST_ADDOPTS="--deselect=tests/ai/personas/test_custom_personas.py" uv run python -c "import pytest; pytest.main(['--collect-only','-q','-n','0','tests/ai/personas/test_custom_personas.py'])"` printed `no tests collected (3 deselected)`, and the same call without it printed `3 tests collected`. So a rerun can leave a file out without a change to `pyproject.toml`. `uv run devops ci test` does not pass this variable to pytest: the same call through it ran `3 passed`. So the probe in task 1.3 is a plain pytest call, which is the call mutmut makes.
- What the first group still proves. Nobody has run the whole method on this tree. Group 1 runs it on the smallest file and records the time. If one mutation command cannot finish inside 14400 s, group 1 stops the item (see `design.md`).

## Existing Tool Considered

mutmut 3.8.0 (a dev dependency, run through `uv run devops ci mutate` and `uv run mutmut`) covers the need. It is an open, maintained tool. The change builds no mutation code. It deletes the test files that the report shows to add no check, from the 17 files in Impact.
