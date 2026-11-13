# Proposal: #5413

## Why

A person cannot start a named fix-plan attempt within 6 hours of the last attempt, and a killed attempt counts with no result (#5413).

- The record of item #5118 (plan pull request #5350) holds an attempt at 03:45:42Z with `fix_plan.attempts` 1 and `fix_plan.result` null: a kill ended the attempt. At 05:17:58Z the pod `fix-plan-5350-r2-zm9b6` logged "Its last fix-plan attempt was at 2026-11-13T03:45:42.510914+00:00, less than 6 hours ago.", and the named retry did nothing.
- Plan pull request #5390 (item #5272) used both attempts of its head `8d08977ffff4` on releases before 0.129.1. The second attempt ended `timeout` after 4049 s, because the review found 3 open findings where the last plan comment listed 1. #5409 fixed that cause in 0.129.1, but the record holds `fix_plan.attempts` 2, so no run can start on this head.
- An eviction, a node drain or a rollout ends an attempt as a deadline kill does: the attempt counts, and nothing records why it ended.

Closes #5413.

## What Changes

- `devops roadmap step fix-plan --skip-wait` leaves out the 6-hour wait for the one item that `--item` or `--pull` names. It needs `--confirm`. The cap of 2 attempts on the head and the cap of 3 revisions stay. The Service never passes it, and the Jobs that a later row starts with `--pull` keep the wait.
- The step records the release of each attempt in `fix_plan.version`. With `--skip-wait`, a head with 2 counted attempts gets one more attempt when the record gives an older release than the current release, or no release. The run logs the reason, and the report shows it.
- A killed attempt has a class. While the command runs, the first SIGTERM raises `AttemptKilled` in the main thread, and the step writes the class in the grace period of the pod. A SIGTERM after the time budget is spent is `deadline`: the attempt counts, the record gets the result `timeout`, and the result line holds `result=timeout`, `class=timeout` and `kill=deadline`. A SIGTERM before that, and a stop of the Service during an attempt, is `evicted`: the record keeps the marks of the attempt before it and adds 1 to `fix_plan.evicted`, with the result `evicted`. This holds for 3 evicted attempts on one head. A later evicted attempt counts. An evicted attempt writes no result line, as a stop of the Service does today, and both classes add 1 to `devops_cli_roadmap_fix_plan_total`. The command exits 75 (`EX_TEMPFAIL`) after an evicted attempt and 143 after a deadline kill.
- The change has a spec delta: the option, the record keys, the rule of the extra attempt and the kill classes are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/fix-plan`: the selection with `--skip-wait`, the release of each attempt, and the classes of a killed attempt.

## Impact

- Code: `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/attempt_kill.py` (new), `src/devops_cli/roadmap/time_budget.py`, `src/devops_cli/commands/roadmap_step_fix_plan.py`, `src/devops_cli/roadmap/stores/store.py` (`FixPlanRecordKey`), `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/telemetry/instruments.py`.
- Tests: `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_budget.py`, `tests/roadmap/test_attempt_kill.py` (new), `tests/commands/test_roadmap_step_fix_plan.py`.
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, a dated line in the status history of ADR 0021, and the generated `docs/commands/roadmap.md` and `docs/TELEMETRY.md`.
- No manifest changes. The Service runs the step as the row `fix_plan`, and the fix-plan Jobs run the runner image, so the change takes effect with the next release of the images.
- The live proof follows the release: a named run `devops roadmap step fix-plan --pull 5390 --skip-wait --confirm` starts and writes its result line.

## Feasibility

- Source at `origin/main` 87e813d5b (0.129.1): `_record_reason` (`src/devops_cli/roadmap/steps/fix_plan.py:365-383`) applies the wait of `fix_plan.at` to each candidate, and `_candidates` (`fix_plan.py:399-418`) sends an item that `--item` or `--pull` names through the same rule. `_attempt` (`fix_plan.py:846-897`) writes `fix_plan.key`, `fix_plan.attempts`, `fix_plan.at` and a null `fix_plan.result` before the first model call, and writes the result only after `revise_plan` returns. `FixPlanRecordKey` (`src/devops_cli/roadmap/stores/store.py:270-286`) has no key for the release. The command (`src/devops_cli/commands/roadmap_step_fix_plan.py`) sets no SIGTERM handler, so Python ends the process on SIGTERM and the null result stays.
- The records, read with `devops gh api repos/dan-petty/devops-cli/issues/<n>` on 2026-11-13: #5118 holds `fix_plan.attempts` "1" and `fix_plan.result` null on head `ccfbab2e9586`. #5272 holds `fix_plan.key` "5390:8d08977ffff4…", `fix_plan.attempts` "2", `fix_plan.result` "timeout" and no `fix_plan.version`, and pull request #5390 is an open draft with `plan/needs-fix` at that head. A read-only call of `select_fix_plan` with the new rule against the live record (one read of the item and one of the pull request, release 0.129.1) leaves #5272 out with the 6-hour wait of the attempt at 14:44:07Z for a run without `skip_wait`, and selects #5390 at head `8d08977ffff4` for a run with it, with the reason "the record gives their release as none, older than this release 0.129.1".
- Kubernetes ends a pod in the same way for an eviction, a node drain and the deadline of its Job (`activeDeadlineSeconds`): SIGTERM, then SIGKILL after `terminationGracePeriodSeconds` (Kubernetes documentation, "Pod Lifecycle", "Termination of Pods", and "Jobs", "Job termination and cleanup"). The CronJob templates `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml` set `activeDeadlineSeconds: 7200` and no grace period, so a pod has the default 30 s, which holds one read and one write of the issue. The pod mounts no service account token (`automountServiceAccountToken: false`), so the step cannot read the condition `DisruptionTarget` of its pod. The time budget is the signal that the step has: the rule of `roadmap.fix_plan.time_budget_seconds` keeps it below the deadline of the Job, so the Job controller sends SIGTERM only after the budget is spent.
- Python runs a handler of `signal.signal` in the main thread, and an exception that it raises comes out where the main thread was. pydantic-ai runs an agent with `pydantic_graph._utils.run_until_complete`, which cancels its task, runs the cleanup and raises the exception again on any `BaseException` (`.venv/lib/python3.14/site-packages/pydantic_graph/_utils.py:88-124`, pydantic-ai of `uv.lock`). `AttemptKilled` is a `BaseException`, so no `except Exception` of a client or a retry catches it.
- `packaging` is a dependency of the project (`pyproject.toml`), and `packaging.version.Version` compares two releases.

## Existing Tool Considered

The Job field `podFailurePolicy` with the rule `onPodConditions: DisruptionTarget` and the action `Ignore` is the Kubernetes tool for an eviction that must not count. It counts the retries of a pod in one Job, and it does not see the record of the item, which counts the attempts on a head over many Jobs and the row of the Service. It is the retry owner of #5412, which makes the fix-plan Jobs, and the exit status 75 of an evicted attempt is the hook for its rule `onExitCodes`. `packaging.version` compares the releases, and the standard library `signal` gives the handler. Cost to build: about 0.5 M tokens and 3 hours. Keep: one option, two record keys and one handler. Fix: about 0.1 M tokens. The change deletes no internal code.

## Dependencies

None. #5379 limits each agent run below the margin of the budget, so a deadline kill becomes rare. #5412 starts fix-plan Jobs from the Service with `--pull` and no `--skip-wait`, and can add `podFailurePolicy` for the exit status 75. #5414 changes the log of the plans that the row leaves out, in another branch.
