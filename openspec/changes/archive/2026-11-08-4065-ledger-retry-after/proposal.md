# Proposal

## Why

The issue #4065 reports that a suspended roadmap row can stay suspended for good after an outage that ended on its own.

`FailureLedger` (`src/devops_cli/roadmap/run.py`) suspends a row after 3 failed rounds in a row on one input digest. Only a new digest ends the suspension. Only the lane that reads changes keeps the digest fixed. `_lane_reads_changes` is true for a lane when one of its rows has a `due_rule`. In the table that is the triage lane, row `intake`, and no other row (`git grep -n "due_rule=" src/devops_cli/roadmap/run.py` gives one line). The status lane and the model lane put the hour of the round into the digest (#2757), so their rows already run again each hour. So an outage that ends on its own never ends the suspension of `intake`, and no alert tells a person about it.

The issues #4060 and #4061 gave the project one table of waits, `RETRY_AFTER`, and the function `retry_after(recorded)`. The stage, refine and intake rows use them. This change makes the ledger use the same table for a suspended row.

## What Changes

- Add the optional field `retry_after` (a time) to each ledger entry. When a failed round reaches the limit of the ledger, or goes past it, the ledger sets it to the time of the round plus `retry_after(<class of the last failure>)`. There is one table: `RETRY_AFTER` in `roadmap/failure.py`. The change adds no second table and no setting.
- `FailureLedger.suspended(repo, job, current, now)` and `FailureLedger.failed(repo, job, current, cause, now)` take the time of the round. The ledger has no clock of its own. A row is suspended when it is at the limit, the digest is the one it failed on, and `now` is before `retry_after` (or the entry has no `retry_after`).
- A row whose `retry_after` has passed runs one probe round (half open). A probe round that fails on the same digest adds 1 to the count and sets a new `retry_after`. A success clears the entry, as before. A new digest ends the suspension at once, as before, and its first failure restarts the count at 1 with no `retry_after`.
- The cause of each failed round is now the failure class (`failure_class_of`, the value of `FailureClass`), not the exception class name. An error that is not a `DevOpsCLIError` (a runner can raise `ValueError` or an HTTP error) has no entry in `CLASS_BY_EXCEPTION`, so the caller gives it `ci_infra`, the class that `retry_after()` also gives to an unknown record. `head_moved` has a wait of zero in `RETRY_AFTER` (the issue says it has no entry; the code at origin/main has `timedelta(0)`). Its row runs again at the next round. This follows the table and needs no branch.
- Gauges. `devops_cli_service_job_suspended` gets the label `class` (labels: `repo`, `row`, `class`). The new gauge `devops_cli_service_job_retry_after_seconds` has the same labels and holds the seconds left, as of the last failure or check of the row, and 0 for a row without a retry time. The issue and its refine text name a label `lane`. No series has one: `FailureLedger` keys its entries by repository and row, and row names are unique in `DEFAULT_DUE_TABLE`. So the labels are `repo`, `row` and `class`.
- The log line `MESSAGES.serve.job_suspended` names the class and the time of the next probe round, and keeps the list of new inputs.
- Alert. `RoadmapServiceRowSuspended` in the group `roadmap-service` of `k8s/monitoring/prometheus-values.yaml`: `max by (repo, row, class) (devops_cli_service_job_suspended{job="roadmap-service"}) > 0`, for 3 hours, warning. It has a promtool case in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` and a row in the alert table of `k8s/README.md`. The acceptance run is `tests/prometheus/test_k8s_monitoring_alerting.py`, which writes the group and the fixture to a temporary directory and runs `promtool test rules`.
- Lanes that read changes: the triage lane only (row `intake`). For the rows of the status lane and the model lane the new time changes nothing that a person sees, because the hourly digest ends their suspension first. The spec delta says so in a scenario.
- Rollout rule for the old ledger file on the volume of the Service. The new field is optional. `_FailedRounds` accepts the entries of 4 fields and of 5 fields, and gets the entry of 6 fields as a third form. An old entry loads with no `retry_after` and keeps the digest rule. The next change of the ledger writes the whole file in the 6-field form. A file that cannot be read still stops the start with an error that names it (`read_state_record`). Rollback hazard: an older image fails to read a file that holds 6-field entries and stops its start. A person rolls back by removing `service-failures.json` first (k8s/README.md item 11). The project keeps no backward compatibility before 1.0.0, so the change adds no shim for the older image.
- Rollout rule for settings. The change adds, removes, renames and tightens no setting. `Settings` is a `BaseSettings` with `extra="ignore"` (`src/devops_cli/config/settings.py`), and the change adds no key to the example ConfigMap or to the live ConfigMap. So no ConfigMap change is needed before the image rolls, and no ConfigMap load test is needed. The ledger file is state on the volume, not a setting; a test holds that an old entry loads.
- The spec delta is observable: a metric label, a metric, a log line and an alert.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-limits`: A job that fails each round is suspended; The Service shows each suspended job; The suspension line names the new inputs; A suspended job runs a probe round after its wait; The Service shows the seconds before the next probe round
- `roadmap-service-alerts`: A row that stays suspended warns

## Impact

- Code: `src/devops_cli/roadmap/run.py` (`FailureLedger`, `_FailedRounds`, `_KeptRounds`, `_count_failure`, `_execute_due_rows`), `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Manifests: `k8s/monitoring/prometheus-values.yaml`
- Tests: `tests/roadmap/test_roadmap_ledger_retry_after.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, and the tests that call the ledger (`tests/github/test_service_limits.py`, `tests/roadmap/test_roadmap_run_failure_ledger.py`, `tests/roadmap/test_roadmap_status_rows.py`, `tests/roadmap/stage/test_roadmap_stage_job.py`, `tests/roadmap/refine/test_roadmap_refine_placeholder.py`, `tests/server/test_service_state_unkept.py`, `tests/telemetry/test_telemetry_instruments.py`)
- Documents: `k8s/README.md` (items 11, 12 and 17 of the Roadmap service, and the alert tables), `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md` only where their wait text becomes wrong

## Feasibility

- I read the code at origin/main `7ce8001a` and the library source in the project virtualenv. I ran no code of the Service.
- `RETRY_AFTER` has 5 keys (`provider` 1h, `parser` 6h, `plan_defect` 6h, `ci_infra` 1h, `head_moved` 0). `CLASS_BY_EXCEPTION` can give only these 5 classes, so every project error has a wait. `failure_class_of(exc)` is typed for `DevOpsCLIError` and raises `StopIteration` for another exception. `_count_failure` gets any `Exception`, so the caller maps a non-`DevOpsCLIError` to `ci_infra` and no new table is needed.
- The row exception that `_count_failure` gets is the exception of the row itself. `RoadmapRunError` wraps the failures of a round after the loop, so the class is not read from the wrapper.
- The gauge `devops_cli_service_job_suspended` is set in `FailureLedger._report_locked` with the labels `repo` and `row`. `GLOBAL_METRICS` has `set_gauge` and `clear_metric` for a whole metric but no way to remove one series. So a row whose class changes would keep the old series at 1. The ledger must set the series of the old class to 0 when the class changes and when the entry clears. The dashboard panel `Service Suspended Rows` (`max by (repo, row)`) reads one series for each class and still shows 1 for a suspended row.
- `FailureLedger` has no clock. `_execute_due_rows` has `current_time`, which `run_due_jobs` takes from its `now` or from `datetime.now(UTC)`. Callers pass an aware time. A naive time would raise `TypeError` at the comparison; no caller passes one.
- `_FailedRounds` is a union of a 5-tuple and a 4-tuple. Pydantic tuples have a fixed length, so the 6-field entry is a third member of the union, and `_KeptRounds` (the written form) becomes six fields. An old entry holds an exception name as its cause; it feeds only the log line and the gauge label, which reads `unknown` for a value that is no class.
- Alert files: `RoadmapServiceRowSuspended` goes in the group `roadmap-service`. promtool is available on this host (`~/.local/bin/promtool`), so `tests/prometheus/test_k8s_monitoring_alerting.py` runs the fixture case.
- The new tests fail on origin/main for the right reason. The ledger file fails on `FailureLedger.failed()` and `suspended()` taking no time and on the cause being the exception name. The alert test fails on the missing rule and on the missing fixture case in the values file. The run output path is in the state file of this item.

## Existing Tool Considered

`pybreaker` 1.4.1 is a dependency already (`src/devops_cli/ai/rag/investigator.py`, `src/devops_cli/valkey/cache.py`). I read its source in the virtualenv: `CircuitBreakerStorage` has the members `name`, `state`, `increment_counter`, `reset_counter`, `increment_success_counter`, `reset_success_counter`, `counter`, `success_counter` and `opened_at`; the ready storages are `CircuitMemoryStorage` and `CircuitRedisStorage`, and none keeps a file. It does not fit, for four reasons that the code shows:

1. The state must survive a restart in the ledger file (`service-failures.json`, #2474). A custom storage would copy that persistence in about ten members, and the file format of the ledger would stay as it is for the digest and the causes.
2. The digest rule (a new input ends the suspension) is not an idea of a circuit breaker. A breaker and the ledger would keep two states that must agree.
3. `CircuitBreaker.call` wraps the call, and an open state raises `CircuitBreakerError` from `before_call`. This changes the control flow of `_execute_due_rows`, which skips a suspended row and does not call it.
4. `reset_timeout` is one value for a whole breaker, but the wait here depends on the class of the last failure (1 hour or 6 hours). So pybreaker would need one breaker for each repository, row and class, or a change of `reset_timeout` before each call.

So the change keeps `FailureLedger` and adds a time field to it. A cheaper option stays rejected: put the hour into the digest of the triage lane too, as #2757 did for the other lanes. It gives no class, no probe round, and a digest that no longer shows the real input. Cost, as the issue states it: about 50,000 tokens and 2.5 hours to build (about 40 lines of code, 6 tests and one alert), about 3,000 tokens a quarter to keep, and about 15,000 tokens and 1 hour to fix. Building with pybreaker and a custom file storage costs about 80,000 tokens and 4 hours. The change deletes no internal code; it adds no table and no setting.

## Dependencies

The issues #4060 and #4061 are merged.
