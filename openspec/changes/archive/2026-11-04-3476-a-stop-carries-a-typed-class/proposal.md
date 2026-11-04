# Proposal

## Why

Issue #3476: the implement job guesses the class of a stop from free text, and the guess is often wrong. Evidence from the issue, for 39 stop comments in one day: 17 carry a wrong or misleading class, and 2 report comments add a second class. A fix step that changed no file gets `plan_defect` or `premise_false` (the classifier reads `already implemented` in the last message of the agent). A lost test, a moved HEAD and a reached output cap fall to the last rule, `ci_infra`. A group that is not ticked gets `test`, because the task text inside the reason holds `devops ci test`. The stop of a fix step also loses the check that failed and its log, so 32 of 36 stop tables show `-` as the last failing command, and the cause of the stop stays inferred. People and later rules, such as the clear rule of #3481, act on the wrong class.

## What Changes

- `FailureClass` gets five classes, each with a row in `ACTION_BY_CLASS`: `no_change_in_fix`, `not_ticked`, `tests_lost`, `head_moved` and `output_cap`.
- Each stop site that knows its cause passes a typed class. The step passes it with `StepOutcome.failure_class`: `head_moved`, `tests_lost`, `not_ticked`, `output_cap`, and for a step with no change, `no_change_in_fix` in a fix step and `plan_defect` in a group step. `_stopped_by` and the scoped-check stop pass it to `_StopError`. The tier decision (`_moves_tier`) reads the same class of the run, not a new classification of the text.
- `classify_failure` reads the text of the failure and the log of a check. It no longer reads the last message of the agent (the field `agent` of `FailureEvidence` goes), and it no longer matches `changed no file` or `task of the group is not ticked` in a reason, because those stops are typed.
- A fix-step stop and a scoped-check stop carry the name of the failed check and the end of its log, with secrets masked. The stop comment shows both. The job record keeps both in the new keys `implement.check` and `implement.check_log`. The table shows the check name as the last failing command.
- The stop comment starts with the failed check. It names the last message of the agent as a claim that no check verified.
- `_report` of the Service reads the item again after it reads the log of the Job and before it decides whether the Job left a stop. A stop that the runner wrote in that time keeps its class.
- A test holds that each value of the label `class` in a panel or alert of `k8s/` that reads `devops_cli_service_implement_failures_total` is a class of the taxonomy.
- The change alters the stop comment, the record and the metric labels, which a consumer observes, so it carries spec deltas.
- The change fits one pull request.

The change does not build recovery from a no-op group (#3460), the clear rule of #3481, or a case for the fault set of #3075.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-failure-taxonomy`: 17 classes, an evidence without the last message of the agent, and the new rows of the action table.
- `roadmap-implement-job`: typed classes at the stop sites, the check and its log in the stop, the order of the comment, the fresh read of `_report`, and the label values of the metric.

## Impact

- Code: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`, `openspec/specs/roadmap-failure-taxonomy/spec.md` and `openspec/specs/roadmap-implement-job/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_implement_step_failure_class.py` (new), `tests/roadmap/test_roadmap_implement_job_scoped.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_implement_step_output_cap.py`, `tests/roadmap/test_roadmap_implement_step_tests_kept.py`, `tests/prometheus/test_implement_failure_labels.py` (new).

## Feasibility

Confirmed on 2026-11-04 at `origin/main` (67d3f473).

- `read_file` on `src/devops_cli/roadmap/failure.py` shows `classify_failure` running `_PREMISE` on `f"{evidence.text}\n{evidence.agent}"`, and `_PLAN` matching `changed no file` and `task of the group is not ticked`. So the agent text and the task text reach the rules, as the issue says.
- The stop comment of #2116 at 2026-11-04T05:14Z (`uv run devops gh api repos/dan-petty/devops-cli/issues/2116/comments`) shows `Failure class: premise_false`, the reason `The agent changed no file.`, `-` as the last failing command of the `fix` row, and a last message with `(already implemented)`. The stop of 04:49Z for the same step shows `plan_defect`. The premise holds.
- `implement_step.py` makes the stops from strings: `_exit_failure` returns `_Failure(<text>)` for a moved HEAD, no change and a lost test; `_unticked_failure` returns text; `_run_turn` handles `OutputCapReached` and keeps only the text. `_stopped_by` in `implement_run.py` passes the diff and the tier moves, and no check and no log. `_fix(check, log)` has both and does not pass them.
- `_report` in `implement_submit.py` takes `item` from the listing of `_unreported` and reads the log of the Job (a request to the cluster API) before it calls `_settles_as_stop(item)`. A runner that writes its stop in that time leaves the report with a stale `In Progress` item, which then classifies the log text as `ci_infra`. The issue infers the race and does not reproduce it. The change reads the item again at that point, which is correct whether or not the race caused #2469 and #2570. A test reproduces the sequence with a log read that writes the stop.
- `grep -rn "implement_failures_total" k8s/ docs/` finds `k8s/README.md` and `docs/ROADMAP_WORKFLOW.md` only. No dashboard and no alert rule in `k8s/` reads the metric today, so no panel needs a new label value. The guard test makes this a rule for later panels.
- The fault set of #3075 does not exist: a search for `3075` in `src`, `tests`, `docs` and `openspec` finds no fault set. The change adds no case to it.
- The fixture is a set of synthetic stop texts, not the 39 real stop texts of the window. It proves the classifier on the stops that have no class from their site. The five typed classes are proven by the tests that run the step and the job, because the classifier does not return them. The real texts cannot be copied from the issue window, because the comments hold task text and agent text of other items. The fixture is built from synthetic stop texts that follow each real pattern the issue names: the fix step with no change and a success claim, a lost test, a moved HEAD, the output cap, the not-ticked stop whose task text holds `devops ci test`, the scoped check with a log, the refused tool, and the stops that already had a right class.
- `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_implement_job_scoped.py` runs offline.
- Fail-to-pass: `uv run devops ci fail-to-pass --base origin/main` replays the new and changed tests on the base tree. 17 tests fail on the base and pass now (one module also fails to import on the base, because the new class names do not exist there).

## Existing Tool Considered

The stop classes are the names of the stop reasons of this job, and `failure.py` already holds the taxonomy (#3065). No open, maintained library classifies the stops of this job, so the change extends the table of the module and adds no new classifier. The change removes code: the match on the agent text, and two patterns of the plan rule. Written cost: about 80,000 tokens to build the change and its tests, about 3,000 tokens a month to keep it, about 15,000 tokens to fix a wrong rule, and about one working day.
