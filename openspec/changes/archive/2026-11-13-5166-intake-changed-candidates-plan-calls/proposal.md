# Proposal: #5166

## Why
Two defects make the job result lines wrong (#5166).

- **Intake.** When another writer changes a candidate between the plan and the write, the write raises `RoadmapItemChangedError`. `apply_intake` says that this case is no failure and that the next plan decides the candidate again (#4042). But `_count_candidate` logs it as `job=intake result=skipped success=false class=head_moved`. Many of these candidates are issues that `devops roadmap intake` in an agent session placed itself. On 2026-11-13, `devops roadmap eval grades --window 24h` gave intake the grade 60 (Ineffective), 133 of 193, and `head_moved` was the only failure class (60 lines). The grade asks for alternatives to a job that works.
- **Stage.** `job=stage item=#1928 result=staged plan_calls=0 gate_returns=0 verify_rounds=1 tokens=2135503`. A staged plan needs at least one plan call, but the line says 0. The count came from the run traces of the plan rows, so an attempt that made no plan run in its own traces wrote 0.

## What Changes
- Intake: a candidate whose write raises `RoadmapItemChangedError` logs no result line. It still adds 1 to `devops_cli_roadmap_intake_candidates_total` with `result=skipped`, as before. The INFO line of the candidate says that another writer, such as a person or another intake run, changed the Item.
- Stage: the planner counts each plan call that it makes to the model. The line takes `plan_calls` from that count, so a client that keeps no trace counts its calls too. An attempt that starts from a kept plan (#4064) has no count of plan calls: the calls that made the plan belong to an earlier attempt. Its line leaves `plan_calls` out and does not write 0. The job grade reads a line with no `plan_calls` as no first pass.
- `docs/roadmap/job-success.md` adds the intake case to the list "Some attempts write no line", and tells when a `stage` line has no `plan_calls`.
- The result lines are an observable output of the Service, so the change has a spec delta.

## Capabilities
- Modified: `roadmap-service-logs`. Two ADDED requirements: a changed intake candidate logs no result line, and the stage line counts the plan calls of the attempt.

## Impact
- Code: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `docs/roadmap/job-success.md`.
- The step `fix-plan` uses the same planner (`revise`). It never reads a kept plan, so its line keeps `plan_calls`, now from the same count.
- No manifest, setting or metric changes. A release is necessary. After the deploy, Loki holds no intake line with `class=head_moved`.
- The change fits one pull request.

## Feasibility
- `src/devops_cli/roadmap/intake/intake.py` at `origin/main` (bc4eacd2b, devops-cli 0.131.0): the `except RoadmapItemChangedError` branch of `apply_intake` calls `_count_candidate(repo, CandidateResult.SKIPPED, number, FailureClass.HEAD_MOVED)`, which emits the counter and calls `log_job_result`. The docstring of `apply_intake` says that this case is no failure (#4042). A new test that makes the write of candidate 2 of 3 raise `RoadmapItemChangedError` finds the line `item=#2 result=skipped class=head_moved` on that commit.
- Loki, 2026-11-13 19:07Z, 24 hours: the intake result lines hold 73 lines with `class=head_moved` and 144 lines with `class=none`. The comment of 2026-11-13 on #5166 gives the grades: 24 hours 133 of 193 with `head_moved` 60, 7 days 179 of 280 with `head_moved` 101, so 179 of 179 without these lines.
- Loki, 7 days: two `staged` lines have `plan_calls=0`: #1928 at 2026-11-12 16:28Z (0.120.0) and #3785 at 18:04Z (0.121.1). Both have `verify_rounds=1` and more than 2 million tokens, so a review client with traces ran. In the 20 minutes before each line, `devops_cli_roadmap_stage_plan_record_total{result="hit"}` rose. The earlier attempt of #1928 on 0.119.0 logged review rounds at 16:03Z and 16:17Z, and a rollout to 0.120.0 then cut it. So each of the two attempts staged a kept plan and made no plan call.
- The issue names a client with no trace as the cause. `run_stage` in `src/devops_cli/roadmap/run.py` always gives the Service a `ToolboxModel`, so the Service plans with a client that keeps traces. A client with no trace plans only when `plan_stage` gets no `ToolboxModel` (for example `model=None`), and a test shows `plan_calls=0` for its staged item on `origin/main`. The change counts the calls in the planner, which covers that client, and leaves `plan_calls` out for a kept plan, which is the cause of the two lines in Loki. Both match the issue: a count from the model calls of the attempt, and no field when no count is possible.

## Existing Tool Considered
None applies: the defects are in the writer of the line, `log_job_result` and its callers. The issue gives the cost to build: about 150,000 tokens and 3 hours. The change deletes the count of plan calls from the run traces in `_Planner.note_attempt`.
