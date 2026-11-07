# Design

## Decisions

- **Set `branch = true` in the `[tool.coverage.run]` table instead of passing `--cov-branch` in the gate command**: One table reaches the gate, the shards and `devops ci coverage`, because coverage.py reads it for every run. A flag in `_resolve_pytest_cmd` would leave the other rows on lines only, and `test_gate_test_step_argv_is_unchanged` pins that argv.
- **Upload from the job `test` rather than from a shard job**: The shards write no XML report; the comment at `.github/workflows/ci.yml:251` says so, and the file appears only after `coverage combine` and `coverage xml` in the aggregate job. One upload gives one artifact per run.
- **Pin `actions/upload-artifact` to `cf430e030ddbb5b0abf93d22962f4752f3646cd9` with `# v7.0.2`**: The same action is already pinned at `.github/workflows/ci.yml:176`, and `test_every_remote_action_is_pinned_to_a_commit_sha` refuses a tag or a branch.
- **Pass `include-hidden-files: true`**: `.data` starts with a dot, and the action skips hidden files by default; the shard upload needs the same input at `.github/workflows/ci.yml:180` for `.data/.coverage`.
- **Run the upload with `if: always()` and the condition of the step that writes the report, and set `if-no-files-found: warn`**: A changed-line gate that fails leaves `.data/coverage.xml` behind, because `coverage xml` runs before diff-cover. A run that writes no report, such as a push to main or a plan-only pull request, warns once instead of turning one failure into two.
- **Keep `fail_under` at 85 and the 90% changed-line gate as it is**: The owner decision of 2026-10-27 drops the raise from this issue, and #2356 owns the floor. The measured branch total of 90.75% keeps the 85% floor green.
- **Assert the settings in the two test files that already own the subject**: `tests/invariants/test_agents_md_claims.py` already reads the coverage floor of `pyproject.toml`, and `tests/invariants/test_workflow_contracts.py` already reads the steps of `.github/workflows/ci.yml`. `docs/TESTING.md:93` puts a new invariant test in its subject's file, never in a parallel file.

## Rejected alternatives

- **Raise `fail_under` to the total that CI measures with branches on**: The owner decision of 2026-10-27 in the issue body strikes the raise out and names #2356 for the floor. `pyproject.toml:241:fail_under = 85` is the owner's figure.
- **Pass `--cov-branch` in the gate command in `src/devops_cli/commands/ci.py`**: `tests/commands/test_ci.py` holds `test_gate_test_step_argv_is_unchanged`, and the shards run the same row, so a flag in one place leaves `devops ci coverage` and the shard rows on lines only.
- **Upload the report from each shard job**: `.github/workflows/ci.yml:251` says the shards write no XML report, so the path would match nothing in a shard and four uploads would carry one file.
- **Pin `actions/upload-artifact` by its `v7.0.2` tag**: `test_every_remote_action_is_pinned_to_a_commit_sha` in `tests/invariants/test_workflow_contracts.py` refuses a reference that is no 40-character commit SHA.
- **Set `if-no-files-found: error`**: A Quality Gate step that fails skips `Changed-Line Coverage` and writes no XML, so an error would report a second failure for one defect.
- **Add a new job that downloads the coverage data and uploads the report**: The aggregate job already holds the combined data and writes `.data/coverage.xml` at `.github/workflows/ci.yml:262`; a second job downloads the data again and adds job time to a check that #3593 measures at 290 s of a 300 s limit.
