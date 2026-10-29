# Tasks

## 1. The records, the setting and the GitHub support

- [x] Add failing tests: the job record keys, `roadmap.implement.in_runner` default and variable, the author of a comment, the three client calls, and the default filter parameter of `parse_filters`
  - Verification: `uv run devops ci test tests/test_roadmap_implement_records.py tests/test_github_client.py`
- [x] Add `ImplementRecordKey`, `IssueComment.author_association` with `seed_comment`, the setting, the constants and defaults, `GitHubClient.get_pull_status`, `update_pull_body` and `comment_on_pull`, and the default parameter of `parse_filters`
  - Verification: `uv run devops ci test tests/test_roadmap_implement_records.py tests/test_github_client.py`

## 2. The fix step

- [x] Add failing tests: the inputs of a fix step with a cut log, its exit checks, its commit title, and a `tasks.md` that it changes
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Add `FixRequest` and the fix mode of `build_step_inputs` and `run_step`, and the instructions of the fix
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_ai_task_implement.py`

## 3. The selection and the plan

- [x] Add failing tests: the default filter, each reason to leave an item out, the retry comment, the limit and the order, and the dry run
  - Verification: `uv run devops ci test tests/test_roadmap_implement_selection.py`
- [x] Add `roadmap/implement.py`: the filter, the judge, the plan, the dry run and the report
  - Verification: `uv run devops ci test tests/test_roadmap_implement_selection.py`

## 4. The run of one item

- [x] Add failing tests: the refusal outside a runner, two groups to a ready pull request, a done group skipped, a conflict on the rebase, a stopped step, and the records
  - Verification: `uv run devops ci test tests/test_roadmap_implement_job.py`
- [x] Add `roadmap/implement_run.py` and `roadmap/implement_pull.py`: the worktree, the rebase, the group loop, the documentation and archive commits, the push with a lease, the body and the comments, the stop, and the finish
  - Verification: `uv run devops ci test tests/test_roadmap_implement_job.py`

## 5. The checks and the fix

- [x] Add failing tests: a check that fails once, a check that fails twice, an old head, a timeout, an open thread and a conflict
  - Verification: `uv run devops ci test tests/test_roadmap_implement_checks.py`
- [x] Add the watch, the log of a failed check, the one fix step, and the ready call
  - Verification: `uv run devops ci test tests/test_roadmap_implement_checks.py tests/test_roadmap_implement_job.py`

## 6. The command and the documentation

- [x] Add failing CLI tests: the job options, the modes, the refusal, the report and the exit code, and the step mode that stays as it was
  - Verification: `uv run devops ci test tests/test_roadmap_implement_command.py`
- [x] Add the job mode to `devops roadmap implement`, its help and messages, the term in `CONTEXT.md`, and the dry-run plan
  - Verification: `uv run devops ci test tests/test_roadmap_implement_command.py tests/test_roadmap_dry_runs.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 7. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2665-implement-job`

## Workflow follow-up

- The runner image, the Job template and the Service's submission of one Job are #2667. The Job template sets `roadmap.implement.in_runner`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
