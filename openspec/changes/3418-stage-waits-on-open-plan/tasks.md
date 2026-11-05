# Tasks

## 1. Find the open plan that creates a missing path

Reads: `src/devops_cli/roadmap/stage_probe.py`, `tests/roadmap/test_roadmap_stage_probe.py`. Changes: `src/devops_cli/roadmap/stage_probe.py`, `tests/roadmap/test_roadmap_stage_probe.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_probe.py`, add `test_missing_path_an_open_plan_creates_is_a_dependency`. It asserts that `blocked_by` of the missing path with `{path: 3308}` gives `(3308,)`, and that a path which the staging commit holds gives `()`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` fails on the base
- [x] 1.2 Add `blocked_by(missing, creators)` to `src/devops_cli/roadmap/stage_probe.py`. It returns the sorted numbers of the open items that create a missing path, with no duplicate
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` passes

## 2. Return an item that needs an open plan, with no model call

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_job.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_job.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_job.py`, add `test_dependency_returns_item_without_model_call`. It seeds an item that cites a missing path, merges the plan of an open item that marks the path `(new)`, and asserts that the round makes no model call for the item, sets the item to New, and records the open item in `refine.blocked_by` with `refine.next_step` set to `blocked`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_job.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_job.py` fails on the base
- [x] 2.2 Make the planner return a blocked outcome when the probe finds a dependency. Read the creates of the open plans once for the run, with `functools.cache`, only when the probe finds a missing path. Return the blocked items from `plan_stage` and write them in `apply_stage`: set the item to New with the recorded blocker, comment the dependency, and render a section in the plan. Rename `refine._recorded_blockers` to `recorded_blockers`. Add the messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_job.py` passes

## 3. Leave out an item with an open recorded blocker

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine.py`, `tests/roadmap/test_roadmap_stage_selection.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_selection.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_stage_selection.py`, add `test_open_recorded_blocker_leaves_item_out` and `test_closed_recorded_blocker_does_not_leave_item_out`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py` fails on the base for the first test
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py` fails on the base
- [x] 3.2 Add `_Judge._recorded_blocker` to `src/devops_cli/roadmap/stage.py`. It names each open item of `recorded_blockers` in the reason, with the message `stage_left_blocked`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py` passes

## 4. Read the create paths of open plans and skip closed plans

Reads: `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_stage_planned.py`. Changes: `src/devops_cli/roadmap/planned.py`, `tests/roadmap/test_roadmap_stage_planned.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_stage_planned.py`, add `test_closed_plan_naming_a_path_is_no_dependency`. It merges the plan of a closed item that marks a path `(new)`, and asserts that the open-plan creates map holds no entry for that path, while the plan of an open item holds it. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_planned.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_planned.py` fails on the base
- [x] 4.2 Add `open_plan_creates(store, source, planned, *, operation)` to `src/devops_cli/roadmap/planned.py`. It maps each path that an active change of an open item marks `(new)` to the number of that item, read with `created_paths` and `tasks_on_default`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_planned.py` passes

## 5. Refuse a plan that creates a path an open plan creates

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 5.1 In `tests/roadmap/test_roadmap_stage_plan.py`, add `test_check_proposal_refuses_path_an_open_plan_creates`. It asserts that `check_proposal` with `plan_creates={path: 3308}` returns one problem that names the path and #3308 for a reply that creates the path, and none for a reply that does not. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 5.2 Add the keyword `plan_creates` to `check_proposal` and the problem sentence `stage_problem_creates` to the messages. In `_Planner._settle`, pass the open creates of the run. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
- [x] 5.3 In `tests/roadmap/test_roadmap_stage_plan.py`, add `test_a_split_reply_that_creates_a_path_an_open_plan_creates_goes_back_to_the_model_once`. A split reply is a plan too. The test asserts that a split group that creates a path an open plan creates goes back to the model once, with a problem that names the path. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails before task 5.4 for this test
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails before task 5.4 for this test
- [ ] 5.4 Rename `_creates_problems` to `creates_problems` in `src/devops_cli/roadmap/stage_change.py`. In the split branch of `_Planner._settle` in `src/devops_cli/roadmap/stage.py`, check the groups of the split reply with `creates_problems`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 6. Remove the dead blocked branch of the stage eval

Reads: `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage.py`. Changes: `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage.py`.

- [ ] 6.1 Delete the `Blocked` branch of `_planned_as` in `src/devops_cli/roadmap/stage_eval_run.py`. In `plan_item` in `src/devops_cli/roadmap/stage.py`, raise `RoadmapStageError` when the planner returns a `Blocked` outcome, and type the result as `StagedChange | OverBudget`. `plan_item` reads no open plan, so the planner never returns `Blocked` there
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py`

## 7. List the task reads of open plans in the dry run

Reads: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [ ] 7.1 In `tests/roadmap/test_roadmap_dry_runs.py`, add `test_the_stage_plan_reads_the_tasks_of_each_open_plan_once_for_the_round`. It asserts that `stage_requests` lists one `git show` of `origin/main:openspec/changes/<change>/tasks.md`, with a condition and a repeat. Verify that `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` fails on the base
- [ ] 7.2 Add the request `open_plan` to `stage_requests` in `src/devops_cli/roadmap/request_plan.py`, with its description, condition and repeat in `src/devops_cli/lang/en/messages.py`. Name the reads of the open plans in the docstring of `stage_requests`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` passes

## 8. Test that an archived plan names no dependency

Reads: `src/devops_cli/roadmap/planned.py`, `tests/roadmap/test_roadmap_stage_planned.py`, `openspec/changes/3418-stage-waits-on-open-plan/specs/roadmap-stage/spec.md`. Changes: `tests/roadmap/test_roadmap_stage_planned.py`, `openspec/changes/3418-stage-waits-on-open-plan/specs/roadmap-stage/spec.md`.

- [ ] 8.1 In `tests/roadmap/test_roadmap_stage_planned.py`, add `test_archived_plan_naming_a_path_is_no_dependency`. It merges the plan of an open item into an archived change that marks a path `(new)`, and asserts that `open_plan_creates` holds no entry for that path.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_planned.py`
- [ ] 8.2 In the spec delta, add the scenario `An archived change names the path` to the requirement `A closed plan is no dependency`.
  - Verification: `uv run devops openspec check`

## 9. Document the return of the stage job

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 9.1 Add a paragraph to `docs/ROADMAP_WORKFLOW.md` that tells how the stage job returns an item whose premise needs an open plan, and how the selection waits on `refine.blocked_by`. Write it in ASD-STE100, with at most six sentences in each paragraph
  - Verification: `uv run devops ci docs`
