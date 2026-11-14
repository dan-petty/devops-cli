# Tasks

## 1. Add the roadmap-stage-eval-commits row and its check

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `tests/gate/configured_domain.py`, `tests/invariants/test_configured_domain_check.py`, `tests/commands/test_ci_gate_rows.py`, `tests/support/paths.py`, `docs/TESTING.md`. Changes: `tests/invariants/test_roadmap_stage_eval_commits_check.py` (new), `tests/gate/roadmap_stage_eval_commits.py` (new), `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci_gate_rows.py`, `docs/TESTING.md`.

- [x] 1.1 Write `tests/invariants/test_roadmap_stage_eval_commits_check.py` first: `test_the_row_fails_on_a_shallow_clone`, `test_the_row_names_each_base_commit_that_git_cannot_resolve`, `test_the_row_names_a_case_that_reads_no_commit_with_no_note` and `test_the_row_passes_with_the_count_of_cases` fail on `ModuleNotFoundError` until the check module exists, and `test_a_gate_row_runs_the_main_of_its_module[roadmap-stage-eval-commits-roadmap_stage_eval_commits]` in `tests/commands/test_ci_gate_rows.py` fails with `KeyError` until the table holds the row
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_stage_eval_commits_check.py tests/commands/test_ci_gate_rows.py` fails on the base
- [x] 1.2 Write the invariant test first, with cases that give `outcome` canned git answers and start no program: a shallow clone gives status 1 and the message that names the missing history; a `resolves` that returns False gives status 1 and a line for each case whose base commit it refuses; a case copied with `model_copy(update={"base_commit": NO_COMMIT, "notes": ()})` gives status 1; and a `resolves` that returns True gives status 0 with the count of cases. Then write `tests/gate/roadmap_stage_eval_commits.py` with `_ROW`, `_READS_NO_COMMIT = "reads no commit"`, `FULL_HASH = re.compile(r"[0-9a-f]{40}")`, `is_shallow(stdout)` that compares the stripped output with `true`, `bad_base_commits(cases, resolves)` that names each case whose base commit is not a full hash that `resolves` accepts and each `NO_COMMIT` case with no note that holds `_READS_NO_COMMIT`, `outcome(cases, shallow, resolves)` that fails on a shallow clone with the message that names the missing history and otherwise prints the findings or the count of cases, `_git(*args)` that runs `git -C REPO_ROOT` with a 60 s bound, and `main(argv)` that loads the cases with `load_cases(REPO_ROOT / CASES_DIRECTORY)`, reads the shallow answer and gives `outcome` a `resolves` that runs `git cat-file -e <sha>^{commit}`. Add `roadmap_stage_eval_commits` to the `ci` block of `src/devops_cli/lang/en/messages.py` as the title of the row, append the `CheckSpec` after the `domain` row of `get_check_specs` with `span_name="ci.step.roadmap_stage_eval_commits"` and `metric_step="roadmap_stage_eval_commits"`, and add the row last to `_GATE_ROWS` in `tests/commands/test_ci_gate_rows.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_stage_eval_commits_check.py tests/commands/test_ci_gate_rows.py` passes
- [x] 1.3 Edit `docs/TESTING.md` to add `roadmap-stage-eval-commits` to the row list and `test_roadmap_stage_eval_commits_check.py` to the invariant test list, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 2. Remove the pytest test that starts git

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`.

- [x] 2.1 Delete `_git` and `test_each_base_commit_of_the_set_is_a_full_hash_of_a_real_commit_or_the_case_reads_none` from `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, and delete the `import subprocess` line. Keep `FULL_HASH`, `NO_COMMIT`, `REPO_ROOT`, `pytest` and `test_each_merge_commit_of_the_set_is_a_full_hash_or_the_case_reads_none` as they are, because the merge hash test reads loaded data and no git history
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes

## 3. Check out the full history in the Static Analysis job

Kind: other. Reads: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`. Changes: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`.

- [x] 3.1 Add `fetch-depth: 0` to the `Check out repository` step of the `static` job of `.github/workflows/ci.yml`. That job runs `devops ci --check --skip test,outdated,actionlint`, so it runs the new row. Its default checkout is a shallow clone of depth 1, and on it the row fails with the message that names the missing history. The `test-shard`, `test`, `service-image` and `runner-image` jobs already set `fetch-depth: 0`. Above the step, add a comment that the `roadmap-stage-eval-commits` row reads the git history. In `test_the_static_job_installs_the_pinned_node_and_openspec_before_the_gate` of `tests/invariants/test_workflow_contracts.py`, change the expected checkout from shallow to `fetch-depth: 0`. Change its docstring to give the reason: the gate runs the row that reads the git history
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py` passes, and `$ uv run devops ci --check --no-cache --only zizmor` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
