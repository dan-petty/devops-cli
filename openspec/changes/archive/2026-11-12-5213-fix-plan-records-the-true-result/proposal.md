# Proposal: #5213

## Why

The step `fix-plan` logs results that did not occur, and it loses work (#5213).

- On #4917 (item #4472) the checks refused the plan of the head at the current commit. The planner wrote a plan that they passed (3 plan calls, 2 gate returns, 7,567,057 tokens), and the review of that plan found no open finding. `_settle` pushes only when the review of the head found an open finding, so the step discarded the gated plan, removed `plan/needs-fix` and posted "The plan stays as it is". The branch keeps the plan that the checks refuse.
- On #4963 (item #2968) the plan reader refused the head. The step dropped the reason and logged "found 0 open finding(s) before the repair and 0 after it. The last plan comment listed 0", though no review ran and the step did not read the comment. The attempt used 1 of the 2 attempts on the head and counted against the `fix_plan` grade with the class `plan_defect`.
- A failed repair, a failure before the review and a stop before the review log a review that did not run, and a stop of the planner gets the class `plan_defect`. `cleared` with no push is a success, and a repair that gives the same plan is a success too.

Closes #5213.

## What Changes

- The step reads the plan of the head before the attempt marks. A plan that the reader refuses ends `unreadable`: the step writes only `fix_plan.at` and `fix_plan.result`, uses no attempt, logs one warning with the file and the masked reason, adds 1 to the counter, and writes no result line.
- `PlanRevision` keeps the gated plan (`gated`, when it is not the same plan as the head) and whether the review of the head ran (`reviewed`), also for a failure after the checks. `same_plan` compares the files that `render_change` gives for two plans.
- The results, in order: `stopped`, `failed`, `revised` or `cleared`, `regated`, `dismissed`, `unchanged`. `regated` pushes the gated plan. Only `revised` and `cleared` are a success.
- The attempt line has one text for each path, and the result line holds `before` and `after` only when the attempt measured them, `stop` for a stop and `step` for a failure. A false premise gets the class `premise_false`, and an open blocker and a head over the budget get no class.
- The review of the head skips the screen of `stage.verify_screen`. `revise_plan` reads the paths that open plans create, so an open blocker stops the repair as it stops the stage job.
- New comment texts for `regated`, `dismissed` and `stopped`. The dry run lists the read of the head before the marks, the marks of an unreadable head and the new conditions.
- The change has a spec delta: the results, the record keys, the comments and the result line are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/fix-plan`: the read before the marks, the gated plan, the result of each attempt, its counts and its comment.

## Impact

- Code: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py` (`PlanRevision`, `same_plan`, `_Planner.revise`, `_Planner._review`, `revise_plan`), `src/devops_cli/roadmap/job_result.py` and `src/devops_cli/roadmap/stores/store.py` (comments), `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`.
- Tests: `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/test_job_result.py`, `tests/commands/test_roadmap_step_fix_plan.py`, `tests/support/roadmap_fix_plan.py`. The real head of #4917 goes to `tests/fixtures/roadmap/plan_heads/4917-ba8cc66fd2f4/`, beside the heads of #4963 and #5032 that #5205 added. The stage comments of #4472, #2968 and #4697 go to `tests/fixtures/roadmap_fix_plan/`.
- Documents: ADR 0021 (one `Status History` line: the body of an accepted record does not change, `docs/adr/README.md`), `docs/roadmap/job-success.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/TELEMETRY.md` (generated), `k8s/README.md` item 23.
- An unreadable plan no longer lowers the `fix_plan` grade, and the 6-hour wait spaces its reads. A `regated` attempt pushes one commit, as a `revised` attempt does.

## Feasibility

- Source at `origin/main` 5645b6385 (0.123.1): `_settle` of `fix_plan.py` pushes only `if before:`, so a gated plan with a clean review is never pushed. `_attempt` writes `fix_plan.at` and the attempt count before `_head_plan`, and its `except PlanReadError` builds `FixPlanAttempt(... FAILED, failure=PLAN_DEFECT)` with no reason. `revise_plan` builds `PlanRevision(failure)` with no `before`. `_failure` gives `plan_defect` to `Blocked`. `_Planner._review` returns no findings when the screen gives the band `continue`.
- Live attempts of 2026-11-12: the fix-plan comment on #4472 of 18:39Z says "The plan stays as it is" for #4917, whose head ba8cc66fd2f4 the checks refuse. The record of #2968 holds 1 attempt on head 9c4b2cf75c64 with `fix_plan.result` `failed`. The fix-plan comment on #4945 records the one true repair, #5053 from 2 open findings to 1.
- `revise_plan` passes no `open_creates` to the planner at `origin/main`, so the planner never returns `Blocked` in this step. The issue names an open blocker as a stop. The change passes the read of the open plans that the stage job uses (`open_plan_creates`), so the stop is real and a test drives it.
- The reader of 0.123.1 (#5205) reads the heads of #4917, #4963 and #5032 (`read_change` of the copied folders gives 4, 4 and 5 groups).
- `_is_first_pass` of `job_grade_report.py` needs each count of `FIRST_PASS_LIMITS`, so a line with no `after` is no first pass.

## Existing Tool Considered

No open tool holds the result rules of this step. The change reuses `render_change`, `log_job_result`, `bounded_text` (masked with `redact_text` and cut to 500 characters) and `open_plan_creates` of the project. Cost to build: about 1.2 M tokens and 4 hours. Keep: the new tests add about 20 s of CI. Fix: about 0.2 M tokens for each wrong result. The change deletes `_failure` of `fix_plan.py` and the text `fix_plan_comment_clean`.

## Dependencies

- #5205
