# Tasks

## 1. Add the record key and the rule that replaces a failing draft

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `tests/roadmap/stores/test_comment_repeat.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage_held.py` (new), `tests/roadmap/stage/test_roadmap_stage_held.py` (new).

- [ ] 1.1 `tests/roadmap/stage/test_roadmap_stage_held.py::test_a_draft_plan_that_fails_check_proposal_is_replaced` fails first: it builds `DraftRead` for a draft whose plan check found a problem and asserts that `may_replace` is true, then asserts the three holds and the bound
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_held.py tests/roadmap/stores/test_comment_repeat.py` fails on the base
- [ ] 1.2 Add the member `RESTAGE = "stage.restage"` to `class StageRecordKey` in `src/devops_cli/roadmap/stores/store.py`, with its sentence in the class docstring, so that every later group reads a key that this group writes. Run `tests/roadmap/stores/test_comment_repeat.py`, the test of that module, so a break in the store shows in this group. Add `src/devops_cli/roadmap/stage/stage_held.py` with `Restage` (the pull and the hash of the item text), `restage_record` and `recorded_restage` for that key, `DraftRead` (the pull, whether it is a draft, the unresolved thread count, the problems of the plan check, the paths outside the change folder, and whether the record holds a re-stage of the same text) and `may_replace`, true only for a draft with no unresolved thread, no path outside the change folder, at least one problem and no earlier re-stage. Add its cases to `tests/roadmap/stage/test_roadmap_stage_held.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_held.py tests/roadmap/stores/test_comment_repeat.py` passes

## 2. Read the one draft pull request of a held item

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_held.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/pr_threads.py`, `src/devops_cli/roadmap/stage/stage_specs.py`. Changes: `src/devops_cli/roadmap/stage/stage_held.py`, `tests/roadmap/stage/test_roadmap_stage_held_read.py` (new).

- [ ] 2.1 `tests/roadmap/stage/test_roadmap_stage_held_read.py::test_a_draft_whose_plan_check_finds_a_problem_is_read_as_replaceable` fails first: a fake client of `src/devops_cli/github/client.py` gives the draft state, the branch's changed paths and its change files, a fake thread read gives no unresolved thread, and `held_draft` returns a read that `may_replace` accepts; the next cases give a passing plan, one unresolved thread and one path outside the change folder
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_held_read.py` fails on the base
- [ ] 2.2 Add `held_draft` to `src/devops_cli/roadmap/stage/stage_held.py`: it returns None when the record holds no `stage.pr`, the pull request is not an open draft, or `origin` holds no such branch. Otherwise it reads the state and the draft flag with `get_pull_status` of `src/devops_cli/github/client.py`, the unresolved threads with `list_pr_review_threads` of `src/devops_cli/github/pr_threads.py`, the changed paths with `get_compare_files`, and the change files at the head commit with `get_file_at`. It builds a `PlanFolder` with those files, the checkout of the job, a `StagedTree` of the branch's paths, the capabilities that `read_base_specs` of `src/devops_cli/roadmap/stage/stage_specs.py` gives, the title and the body of the item, and the budget and the registry of the job, then calls `folder_problems` of `src/devops_cli/roadmap/plan_check.py` on it: a non-empty list is the plan check that fails. It marks a re-stage when `recorded_restage` holds the hash of the item's text. The client, the thread read and the checkout are arguments, so a test passes fakes to `tests/roadmap/stage/test_roadmap_stage_held_read.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_held_read.py` passes

## 3. Let a failing draft stop holding the item

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_held.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`.

- [ ] 3.1 `tests/roadmap/stage/test_roadmap_stage_selection.py::test_a_held_item_whose_draft_plan_fails_check_proposal_is_staged_again` fails first; `test_a_held_item_with_a_passing_plan_a_thread_or_a_commit_beyond_the_plan_stays_out` covers the three holds, and `test_a_re_staged_item_is_held_with_the_failed_check_proposal` covers the bound
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py` fails on the base
- [ ] 3.2 Add the field `replace_pull: int | None = None` to `class StageTarget` in `src/devops_cli/roadmap/stage/stage.py`. Give `select_stageable` and `_Judge` the argument `draft_of: Callable[[Item], DraftRead | None]`, and let `_held` return None when `may_replace` holds; the verdict of `select_stageable` and `_named_item` put the pull of the read on the target they build. When `recorded_restage` holds the hash of the item's text, `_held` returns the reason that names the failed plan check, and otherwise the current reason. `read_stage_selection` passes `draft_of` from `held_draft` of `src/devops_cli/roadmap/stage/stage_held.py` with the checkout, the client of the session and the default branch of `planned`. Update the held-item sentence of the module docstring, and add the three cases to `tests/roadmap/stage/test_roadmap_stage_selection.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py` passes

## 4. Replace the draft on its branch and name it

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_held.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_restage.py` (new).

- [ ] 4.1 `tests/roadmap/stage/test_roadmap_stage_restage.py::test_a_re_stage_pushes_to_the_same_branch_updates_its_draft_and_names_it` fails first: it stages a target with `replace_pull` and asserts the push with the lease on the recorded commit, the one `update_pull`, the record `stage.restage`, and the comment that names the draft
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_restage.py tests/roadmap/stage/test_roadmap_stage_apply.py` fails on the base
- [ ] 4.2 In `src/devops_cli/roadmap/stage/stage.py`, push in `_commit_and_push` with `--force-with-lease=refs/heads/<branch>:<stage.sha>` when the target carries `replace_pull`: the worktree takes over the pushed branch and `_rebase_onto_default` can rewrite its tip, so the push is no fast-forward. In `_stage_one`, call `update_pull` with the new title and body instead of `_open_pull`, pass the updated draft to the label steps, and record `stage.restage` with the pull and the hash of the item's text; a fresh stage clears that key. Add the message to `src/devops_cli/lang/en/messages.py` that names the replaced draft, and put its line in the comment of the item. Add its case to `tests/roadmap/stage/test_roadmap_stage_restage.py`, and keep the cases of `tests/roadmap/stage/test_roadmap_stage_apply.py` passing
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_restage.py tests/roadmap/stage/test_roadmap_stage_apply.py` passes

## 5. Document the held rule and the replaced draft

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`.

- [ ] 5.1 State in `docs/ROADMAP_WORKFLOW.md` that a pushed branch holds an item unless its one draft pull request fails the plan check with no unresolved review thread and no path outside the change folder, and that the job then stages the item again on that branch, pushes with a lease on the recorded commit, updates the same draft and names it in the comment. State in `CONTEXT.md` under **Staged** that a re-stage updates the one draft pull request of the item and opens no second one
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/ROADMAP_WORKFLOW.md` and `CONTEXT.md` to state the narrowed held rule, the replaced draft and the one re-stage
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A test asserts that a held item whose draft plan fails `check_proposal` is staged again on its branch.
- Group 3: A test asserts that a held item with a passing plan, with a review thread, or with a commit beyond the plan is still left out, with its current reason.
- Group 4: The stage report names the draft pull request that the job replaced.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
