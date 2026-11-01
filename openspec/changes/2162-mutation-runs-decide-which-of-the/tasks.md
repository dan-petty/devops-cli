# Tasks

## 1. Record the base, prove the method on the smallest file

Reads: `tests/ai/personas/test_custom_personas.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `pyproject.toml` (the `[tool.mutmut]` table, lines 255 to 290). Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` (new), and `tests/ai/personas/test_custom_personas.py` if its verdict is `delete`.

- [ ] 1.1 Run `uv run devops ci coverage` and write its total line coverage as the line `Base line coverage: <percent>%` at the top of the new `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, with the heading `# Mutation report` and the table header of the Method in `design.md`. Verify that `grep -E '^Base line coverage: [0-9.]+%$' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints the line
- [ ] 1.2 Build `mutants/` and its test stats with `uv run devops ci mutate src/devops_cli/ai/personas/__init__.py`. Write in the report the run time of the command and the `mutations/second` that mutmut prints. If the command does not end inside 14400 s, apply the stop rule of `design.md`. Verify that `jq 'keys' mutants/mutmut-stats.json` prints the keys `duration_by_test` and `tests_by_mangled_function_name`
- [ ] 1.3 Check that `PYTEST_ADDOPTS` leaves a file out: run `PYTEST_ADDOPTS="--deselect=tests/ai/personas/test_custom_personas.py" uv run pytest --collect-only -q -n 0 tests/ai/personas/test_custom_personas.py` and write its last line in the report. Verify that the last line is `no tests collected (3 deselected)` followed by a time
- [ ] 1.4 Apply the Method of `design.md` to `tests/ai/personas/test_custom_personas.py` and write its row in the report. Verify that `grep -c '^| tests/ai/personas/test_custom_personas.py ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `1`
- [ ] 1.5 If the verdict is `delete`, remove the file with `git rm tests/ai/personas/test_custom_personas.py`. Verify that `git ls-files tests/ai/personas/test_custom_personas.py` prints nothing for a deleted file, or the path for a kept file, and that `uv run devops ci test tests/ai/personas` passes

## 2. Decide the four schema and parser files

Reads: `tests/ai/test_review_advisory_backing.py`, `tests/ai/test_review_location_paths.py`, `tests/ai/test_review_loop_hardening.py`, `tests/ai/test_structural_positional_oracles.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and each of the files above with the verdict `delete`.

- [ ] 2.1 Apply the Method of `design.md` to each file in the order listed above, and write one row for each in the report. Verify that `grep -cE '^\| (tests/ai/test_review_advisory_backing\.py|tests/ai/test_review_location_paths\.py|tests/ai/test_review_loop_hardening\.py|tests/ai/test_structural_positional_oracles\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `4`
- [ ] 2.2 Remove each file with the verdict `delete` with `git rm`. Check each removed file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/ai/test_review_advisory_backing.py tests/ai/test_review_location_paths.py tests/ai/test_review_loop_hardening.py tests/ai/test_structural_positional_oracles.py` prints only the files with the verdict `keep`, and that `uv run devops ci test tests/ai` passes

## 3. Decide the two scanner files

Reads: `tests/security/test_sarif_fuzzing.py`, `tests/security/test_security_kubelinter.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and each of the files above with the verdict `delete`.

- [ ] 3.1 Apply the Method of `design.md` to each file in the order listed above, and write one row for each in the report. The files of this group are in `tests/security/`: read each before you call it a test of a guard. Verify that `grep -cE '^\| (tests/security/test_sarif_fuzzing\.py|tests/security/test_security_kubelinter\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `2`
- [ ] 3.2 Remove each file with the verdict `delete` with `git rm`. Check each removed file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/security/test_sarif_fuzzing.py tests/security/test_security_kubelinter.py` prints only the files with the verdict `keep`, and that `uv run devops ci test tests/security` passes

## 4. Decide the four review files that run few modules

Reads: `tests/ai/review/test_review_defects_comments.py`, `tests/ai/review/test_review_taxonomy_and_severity.py`, `tests/ai/review/test_review_deduplication.py`, `tests/ai/review/test_review_regression_harness.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and each of the files above with the verdict `delete`.

- [ ] 4.1 Apply the Method of `design.md` to each file in the order listed above, and write one row for each in the report. Verify that `grep -cE '^\| (tests/ai/review/test_review_defects_comments\.py|tests/ai/review/test_review_taxonomy_and_severity\.py|tests/ai/review/test_review_deduplication\.py|tests/ai/review/test_review_regression_harness\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `4`
- [ ] 4.2 Remove each file with the verdict `delete` with `git rm`. Check each removed file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/ai/review/test_review_defects_comments.py tests/ai/review/test_review_taxonomy_and_severity.py tests/ai/review/test_review_deduplication.py tests/ai/review/test_review_regression_harness.py` prints only the files with the verdict `keep`, and that `uv run devops ci test tests/ai/review` passes

## 5. Decide the defenses and verification file

Reads: `tests/ai/review/test_review_defenses_and_verification.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and the file above if its verdict is `delete`.

- [ ] 5.1 Apply the Method of `design.md` to the file, and write its row in the report. Verify that `grep -cE '^\| (tests/ai/review/test_review_defenses_and_verification\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `1`
- [ ] 5.2 If the verdict is `delete`, remove the file with `git rm`. Check the file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/ai/review/test_review_defenses_and_verification.py` prints the path only for the verdict `keep`, and that `uv run devops ci test tests/ai/review` passes

## 6. Decide the history file

Reads: `tests/ai/review/test_review_history.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and the file above if its verdict is `delete`.

- [ ] 6.1 Apply the Method of `design.md` to the file, and write its row in the report. The file runs 307 functions in 44 modules. Run the mutants in one `uv run mutmut run` for each module of its functions, so that no command passes 14400 s. Verify that `grep -cE '^\| (tests/ai/review/test_review_history\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `1`
- [ ] 6.2 If the verdict is `delete`, remove the file with `git rm`. Check the file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/ai/review/test_review_history.py` prints the path only for the verdict `keep`, and that `uv run devops ci test tests/ai/review` passes

## 7. Decide the verification file

Reads: `tests/ai/test_review_verification.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and the file above if its verdict is `delete`.

- [ ] 7.1 Apply the Method of `design.md` to the file, and write its row in the report. The file runs 246 functions in 35 modules. Run the mutants in one `uv run mutmut run` for each module of its functions. Verify that `grep -cE '^\| (tests/ai/test_review_verification\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `1`
- [ ] 7.2 If the verdict is `delete`, remove the file with `git rm`. Check the file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/ai/test_review_verification.py` prints the path only for the verdict `keep`, and that `uv run devops ci test tests/ai` passes

## 8. Decide the two review command files

Reads: `tests/commands/test_review.py`, `tests/commands/test_review_removed_options.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and each of the files above with the verdict `delete`.

- [ ] 8.1 Apply the Method of `design.md` to each file in the order listed above, and write one row for each in the report. Verify that `grep -cE '^\| (tests/commands/test_review\.py|tests/commands/test_review_removed_options\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `2`
- [ ] 8.2 Remove each file with the verdict `delete` with `git rm`. Check each removed file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/commands/test_review.py tests/commands/test_review_removed_options.py` prints only the files with the verdict `keep`, and that `uv run devops ci test tests/commands` passes

## 9. Decide the cited code file

Reads: `tests/ai/review/test_cited_code.py`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and the file above if its verdict is `delete`.

- [ ] 9.1 Apply the Method of `design.md` to the file, and write its row in the report. The file runs 264 functions in 39 modules. Run the mutants in one `uv run mutmut run` for each module of its functions. Verify that `grep -cE '^\| (tests/ai/review/test_cited_code\.py) ' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints `1`
- [ ] 9.2 If the verdict is `delete`, remove the file with `git rm`. Check the file against the exempt list of `design.md` and write the check in the report. Verify that `git ls-files tests/ai/review/test_cited_code.py` prints the path only for the verdict `keep`, and that `uv run devops ci test tests/ai/review` passes

## 10. Check coverage, the deleted set and CI

Reads: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, `openspec/changes/2162-mutation-runs-decide-which-of-the/design.md`. Changes: `openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md`, and the covering files of `design.md` only if the line coverage fell.

- [ ] 10.1 Run `uv run devops ci coverage` and write its total in the report as `Final line coverage: <percent>%`. Verify that `grep -E '^(Base|Final) line coverage' openspec/changes/2162-mutation-runs-decide-which-of-the/mutation-report.md` prints both lines, and that the final value is not below the base value and not below 85, which is `fail_under` in `pyproject.toml`
- [ ] 10.2 If the final value is below the base value, move the tests that run the lost lines into the covering file of the row in `design.md`: take them from `git show origin/main:<deleted path>`, put them in the covering file, and repeat 10.1 until the value is not below the base. Write each moved test in the report. Skip this task when 10.1 passes
- [ ] 10.3 Check the deleted set: `git diff --name-only --diff-filter=D origin/main...HEAD` must print only paths of the 17 files in `proposal.md`, and no path in `tests/invariants/` or with `contract` in its name. Verify that `git diff --name-only --diff-filter=D origin/main...HEAD | grep -E 'tests/invariants/|contract'` prints nothing
- [ ] 10.4 Verify that `uv run devops openspec check` and `uv run devops ci` pass

## Workflow follow-up

- Pending a person: compare the duration of the `Tests & Coverage` job in the check runs of the pull request with the same job on `main`. The `Test Job Duration` job of `.github/workflows/ci.yml` fails above 300 s, and deleted tests cannot lengthen the job.
