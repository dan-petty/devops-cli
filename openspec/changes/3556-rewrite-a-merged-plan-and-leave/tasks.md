# Tasks

## 1. Add the mechanical rewrite of a plan

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/plan_rewrite.py` (new), `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_rewrite.py` (new).

- [x] 1.1 In `tests/roadmap/test_roadmap_plan_rewrite.py`, write first: `rewrite_plan` on a plan whose groups have no `Verification:` line returns the same groups in the same order, with one new line in each group that names a test file or only documents, and `read_verification` accepts each new command; a behavior group gets the `fails on the base` form and any other group gets the `passes` form; a group that changes no test file and no document gets no line; a task that names `tests/test_sample.py`, which the tree lacks and no group lists, names `test_sample.py` afterwards, and a path in `Reads:`, in `Changes:` or marked `(new)` stays as it is; a folder with no `design.md` gets a stub that `read_change` reads; a plan that needs no change comes back as it was
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_rewrite.py` fails on the base
- [x] 1.2 Create `rewrite_plan` in `src/devops_cli/roadmap/plan_rewrite.py`. Make `group_files` public in `src/devops_cli/roadmap/plan_read.py`, add the field `line` to `TaskGroup` in `src/devops_cli/roadmap/step_files.py`, and add the stub text and the notes to `src/devops_cli/lang/en/messages.py`. Edit by the line numbers of `parse_task_groups`, so that every other line stays as it is
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_rewrite.py tests/roadmap/test_roadmap_plan_recheck.py` passes

## 2. Judge the rewritten plan in the recheck

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_rewrite.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/stage_validate.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_recheck.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_plan_recheck.py`, write first: a plan with a group that has no `Verification:` line and that changes a test file gets `rewrite` and still counts as unreadable and unverified; a plan whose rewritten text still fails a gate gets `new-plan` with the refusal of the rewritten plan; a plan whose group changes no test file and no document gets `new-plan` with the reader error; a plan that passes and that the rewrite does not change gets `ok`; a `rewrite` record holds the changed files
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` fails on the base
- [x] 2.2 In `_record` of `src/devops_cli/roadmap/plan_recheck.py`, call `rewrite_plan`, read and judge the rewritten files with `read_change`, `check_gates` and `validate_change`, keep the readability and the verification of the merged plan for the counts, and give each `rewrite` record the changed files. Delete the note `plan_recheck_no_verification` and the rule that gave `rewrite` before any rewrite
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` passes

## 3. Write the rewrite with confirm

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_rewrite.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/plan_rewrite.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py` (new).

- [x] 3.1 In `tests/commands/test_roadmap_plan_recheck_cmd.py`, write first: without `--confirm` the working tree of a checkout holds no changed file; `--confirm --source <checkout>` writes the changed files of each `rewrite` folder and makes no commit; `--confirm` without `--source` exits with an error that names `--source`; `--confirm` with `--dry-run` exits with an error; a file that differs from the default branch stops the write before any file is written and the error names it
  - Verification: `uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py` fails on the base
- [x] 3.2 Add `write_rewrite` to `src/devops_cli/roadmap/plan_rewrite.py`. Add the option `--confirm` to `plan_recheck_cmd` in `src/devops_cli/commands/roadmap.py`, with `_one_mode` for `--dry-run` and `--confirm`, and add the help and message texts. Check every file before the first write
  - Verification: `uv run devops ci test tests/commands/test_roadmap_plan_recheck_cmd.py tests/roadmap/test_roadmap_dry_runs.py` passes

## 4. Hold the left-out reason of a Planned item

Kind: other (a test-only edit; it changes no behavior). Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/test_roadmap_implement_plan_reason.py`, `tests/support/roadmap_implement.py`. Changes: `tests/roadmap/test_roadmap_implement_plan_reason.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_implement_plan_reason.py`, add a test for a Planned item whose merged plan holds the task `1.1 x`: `plan_implement` selects no target and `explain_item` names the first problem with the reason `implement_left_plan`. Add a test for a merged plan that the rewrite can not fix, to show that it leaves the queue with the same reason
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_plan_reason.py` passes

## 5. Say what the rewrite does

Reads: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/lang/en/help.py`. Changes: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`.

- [ ] 5.1 In `docs/roadmap/plan-recheck.md`, state the three edits of the rewrite, the rule for the result `rewrite`, the option `--confirm` with its checks, and that the left-out reason of #3393 holds a plan with no way forward. In `docs/ROADMAP_WORKFLOW.md`, replace "writes nothing" with the rule for `--confirm`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
