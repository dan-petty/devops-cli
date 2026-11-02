# Tasks

## 1. Add the readiness function and its table test

Reads: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/client.py`, `src/devops_cli/git/branch_form.py`. Changes: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_draft_readiness.py` (new).

- [ ] 1.1 In the new `tests/roadmap/test_roadmap_draft_readiness.py`, add a table test of eight rows, four kinds with one complete and one incomplete row each: a stage plan with passing checks is ready and one with a failed check is refused, an implement pull request with every group ticked and archived is ready and one with group 2 unticked is refused with a reason that names group 2, an agent and a person that declared are ready and ones that did not wait. Add tests for a running check (wait), for `checks=None` (the checks rule is skipped), for an unarchived change with every group ticked (refuse), for a missing change (refuse), and for an extra check that refuses a complete draft. Add a test of `kind_of` over four items (`implement.pr`, `owner/agent`, `stage.pr`, no record), one over an item that holds `stage.pr` and `owner/agent` (agent), and one over no item (person). Verify that `uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` fails on the base
- [ ] 1.2 Add `DraftKind`, `Answer`, `Readiness`, `ChangeFacts`, `Draft`, `draft_readiness` and `kind_of` to `src/devops_cli/roadmap/implement_pull.py`, with the reasons in `src/devops_cli/lang/en/messages.py`. `draft_readiness` tests completeness first, then `checks.exit_code` when `checks` is not None, then each extra check. `kind_of` follows the order of the design. The reason for an unticked group reads "Task group {number}, {title}, has a task that is not ticked." Verify that `uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` passes

## 2. Route the stage row through draft_readiness

Reads: `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_stage_ready.py`. Changes: `src/devops_cli/roadmap/stage_ready.py`, `tests/roadmap/test_roadmap_stage_ready.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_ready.py`, replace the monkeypatch of `stage_ready.ready_to_mark` (line 342) with a monkeypatch of `stage_ready.draft_readiness` that answers refuse, and assert that the round marks nothing. Delete `test_ready_to_mark_is_true_for_passing_checks_only` and drop `StageDraft` and `ready_to_mark` from the import: the cases move to group 1. The tests of a failed, cancelled, running and missing check run keep their rows and now go through the row. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_ready.py` fails on the base
- [ ] 2.2 In `src/devops_cli/roadmap/stage_ready.py`, delete `ready_to_mark` and `StageDraft`. `_settle` builds `Draft(DraftKind.STAGE_PLAN, status, item, checks)`, asks `draft_readiness`, and marks the pull request only on ready. Write the module text with `draft_readiness` in place of `ready_to_mark`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_ready.py` passes

## 3. Route the implement job through draft_readiness

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_failure.py`.

- [ ] 3.1 In `tests/roadmap/test_roadmap_implement_job.py`, add two tests with the `job_world` fixture. In the first, a replacement of `archive_effect` leaves one unticked task in group 2 of the archived `tasks.md`: assert that the item is Blocked at the step `ready`, the reason names group 2, the stop comment starts with the class `plan_defect`, and no `gh pr ready` ran. In the second, the check runs of the head hold a running check when the job reads them before the mark: assert Blocked, the reason says a check runs, and no `gh pr ready` ran. Add the phrase of the unticked group to `tests/roadmap/test_roadmap_failure.py` as a `plan_defect` row. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_failure.py` fails on the base
- [ ] 3.2 In `_ready` of `src/devops_cli/roadmap/implement_run.py`, read the pull request with `get_pull_status`, the check runs of the head with `read_check_runs`, and the archived `tasks.md` in the worktree, ask `draft_readiness` with kind `IMPLEMENT`, and raise `_StopError(self.step, reason)` on any answer but ready, before `mark_ready`. Add `|has a task that is not ticked` to the plan-defect rule of `src/devops_cli/roadmap/failure.py`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_failure.py` passes

## 4. Decide devops pr ready with draft_readiness

Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/client.py`, `tests/commands/test_pr.py`, `tests/support/roadmap.py`. Changes: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr.py`.

- [ ] 4.1 In `tests/commands/test_pr.py`, patch `get_roadmap_store` as `tests/support/roadmap.py` does, and add four tests with the fake GitHub edges. A draft on branch `fix/7-x` whose item holds `implement.pr` 335 and whose `tasks.md` at the head has group 2 unticked: `pr ready` exits 1, prints group 2, and runs no `gh pr ready`. The same draft with every group ticked in the archived `tasks.md`: exit 0 and `gh pr ready` ran. A refused read of the item: exit 1 with the error, and with `--force` the pull request is marked. A branch that names no issue: exit 0 with no read of the item. The five rows of `test_pr_ready_exits_on_the_checks_of_the_verdict` stay as they are. Verify that `uv run devops ci test tests/commands/test_pr.py` fails on the base
- [ ] 4.2 Add `read_draft` to `src/devops_cli/roadmap/implement_pull.py`: it reads the item of the head branch with `issue_of_branch` and `store.item`, takes the kind from `kind_of`, and for kind `IMPLEMENT` reads the files of the pull request and the `tasks.md` at the head with `get_file_at`. In `src/devops_cli/commands/pr.py`, delete `_ready_check_blockers`. `_validate_pr_ready` asks `draft_readiness` with `checks=verdict.checks` and `declared=True`, exits 1 for refuse and 8 for wait with the reason, and keeps the warnings for the other blockers. Update the help text of `ready_pr`. Verify that `uv run devops ci test tests/commands/test_pr.py` passes

## 5. Block check-readiness on a refused implement pull request

Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr.py`.

- [ ] 5.1 In `tests/commands/test_pr.py`, add three tests of `pr check-readiness 335`. For an implement pull request with group 2 unticked: exit 1, the output names group 2, and one readiness blocker. For one with every group ticked and archived: no readiness blocker. For a branch that names no issue: no readiness blocker and no read of the item. Add a fourth test for a refused read of the item: a blocker that names the error. Verify that `uv run devops ci test tests/commands/test_pr.py` fails on the base
- [ ] 5.2 Add `READINESS` to `BlockerKind` in `src/devops_cli/github/merge_readiness.py`. In `check_readiness` of `src/devops_cli/commands/pr.py`, call `read_draft` and `draft_readiness` with `checks=None` and `declared=not draft`, and append one `Blocker(BlockerKind.READINESS, reason)` with `dataclasses.replace` when the answer is refuse. Add the blocker text and the unread text to `src/devops_cli/lang/en/messages.py`. Update the help text of `check_readiness`. Verify that `uv run devops ci test tests/commands/test_pr.py` passes

## 6. Say in the documents that one function decides

Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`, `CONTEXT.md`, `k8s/README.md`. Changes: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`, `CONTEXT.md`, `k8s/README.md`.

- [ ] 6.1 In `k8s/README.md` (row 18), replace `ready_to_mark` with `draft_readiness`. In `docs/roadmap/implement.md`, step 8, say that the job asks `draft_readiness` and stops with the reason on a refusal. In `docs/ROADMAP_WORKFLOW.md`, remove the line of #2916 from "Planned changes" and say in the Verify row that the Job and `devops pr ready` ask one function. In `docs/SDLC.md`, add to the line about `devops pr check-readiness` that it blocks an implement pull request with an unticked task group. In `CONTEXT.md`, add the term **Draft readiness** and mention it in **Implementing**. Verify that `! git grep -n -e ready_to_mark -e StageDraft -e _ready_check_blockers -- src tests docs k8s README.md CONTEXT.md` passes
- [ ] 6.2 Run `uv run devops docs generate --sync-readme` for the new help text of `devops pr ready` and `devops pr check-readiness`, and verify that `uv run devops ci docs` passes

## Criteria

- A test table covers the four kinds with complete and incomplete cases.: group 1
- The implement Job and the stage row use the function.: group 3
- A partial implement pull request is refused by `check-readiness` with the group named.: group 5
- `uv run devops ci` passes.: pending-person, the full suite is the check of the pull request itself and no one group can run it again as its verify. A person reads its result before the merge

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
