# Proposal: #5363

## Why

The step `fix-plan` has no time budget of its own, and a Job that runs it writes no line until the attempt ends. On 2026-11-13 the fix-plan Job on plan pull request #5350 (item #5118) ran from 03:47Z to its `activeDeadlineSeconds` of 5400 s. Kubernetes stopped the pod (`DeadlineExceeded`), and the attempt left no result line, no comment and no count. Its `fix_plan.at` mark still started the 6-hour wait, so a second Job at 05:16Z took no plan. The rule of nested timeouts says that the inner limit fires first, with a margin, and ends with a diagnostic.

Closes #5363.

## What Changes

- The new setting `roadmap.fix_plan.time_budget_seconds` (default 3600) starts with each call of the step. The planner compares the time with it before each plan run and each review run, and starts no run once it is spent (`TimeBudget`, `RoadmapTimeBudgetError`). The step passes the failure class `timeout` itself, as each stop site that knows its cause does (#3476).
- An attempt that spends the budget ends with the new result `timeout`. The step pushes nothing, keeps `plan/needs-fix`, and posts one comment with the marker that names the budget and the step in which it ended, gives the counts of the attempt and lists the open findings that keep the label. The result line holds `result=timeout`, `class=timeout` and `step`. The record keeps the attempt, so the 6-hour wait follows a real result.
- Each review of an attempt logs one progress line: `fix-plan progress: repo=<owner/repo> item=#<n> round=<n> open=<n> tokens=<n> seconds=<n> budget=<n> version=<version>`.
- `devops roadmap step fix-plan` writes the lines of `round_log` and `job_result` to stderr while it runs. A Job runs the command, and before this change its log held only the report at the end.
- The change has a spec delta: the result, the comment, the result line and the progress line are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/fix-plan`: the time budget of the step, the result `timeout` and the progress line of each review.

## Impact

- Code: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage.py` (`_Planner`, `_planner_of`, `revise_plan`), `src/devops_cli/roadmap/time_budget.py` (new), `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/roadmap/job_result.py` (comment), `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`.
- Tests: `tests/roadmap/steps/test_roadmap_fix_plan_budget.py` (new), `tests/commands/test_roadmap_step_fix_plan.py`, `tests/invariants/test_k8s_manifests.py`.
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLUSTER.md` item 23, and the generated `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ERRORS.md` and `docs/TELEMETRY.md`.
- No manifest under `k8s/` changes. The default of the new setting applies with no ConfigMap change.
- Release: the Service runs the row `fix_plan` from its image, and a Job runs the command from the same image, so the fix needs a release and a roll of the image.

## Feasibility

- Source at `origin/main` 4ef7c6f11 (0.127.0): `git grep -n "time_budget\|deadline\|monotonic" src/devops_cli/roadmap/steps/fix_plan.py` finds nothing, and `revise_plan` in `stage.py` measures the seconds of the attempt only for the result line (`clock.monotonic()`). `raise_if_service_stops` is the only check before a plan run or a review run.
- Where the product sets a Job deadline: `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml` set `activeDeadlineSeconds: 7200`, and `devops k8s run-job` copies it (`src/devops_cli/k8s/cluster_job.py`). The Service runs the row `fix_plan` in its own pod, with no Job. The fix-plan Jobs of 2026-11-12 and 2026-11-13 were applied by hand outside git (`kubectl get jobs -n devops`, label `app.kubernetes.io/name=roadmap-fix-plan-validation`) with 5400 s, and `fix-plan-5350-r2` with 10800 s. The default 3600 s plus a margin of 1200 s for one more run, the push and the comment ends before 5400 s and 7200 s, and `test_the_fix_plan_time_budget_ends_before_the_deadline_of_each_job_template` holds the margin against the CronJob templates.
- Run times: the Tempo trace `fbef6e37a8678ee158d313142a3f044e` of the attempt on #5350 holds agent runs of 93 s to 757 s. The Loki lines of the fix-plan Jobs give 2387 s (`cleared`), 2745 s (`cleared`) and 3016 s (`revised`) for the attempts that repaired a plan, and 3272 s (`unchanged`) and 4721 s (`regated`) for the others.
- Why the Job log was empty: Loki shows only the 3 report lines and `Elapsed:` for each fix-plan Job, all at the end. The CLI sets no handler for `logging`, so the INFO lines of `round_log` (for example `stage review round:`) and `job_result` went nowhere. The Service writes the same lines in its JSON log.
- Limit: the budget stops the attempt only at the next plan run or review run. No span of the trace of #5350 ends after 04:38:18Z, and the pod ran until 05:17Z, so one call or wait did not end for 39 minutes. A cooperative budget cannot stop that call. #5379 finds its cause.

## Existing Tool Considered

The issue names `asyncio.timeout` of the standard library. The planner and its agent runs are synchronous (`agent.run_sync`), so `asyncio.timeout` does not apply, and a signal or a thread that interrupts a call at a random point can stop a push or a write of the record halfway. The change compares the `devops_cli.core.clock` seam with the setting at the two safe points, as `raise_if_service_stops` already does, and the stdlib `logging.StreamHandler` writes the lines to stderr. Cost to build: about 0.3 M tokens and 2 hours. Keep: one small module and two short tests. Fix: about 0.05 M tokens for each wrong count.
