# Tasks

## 1. Keep the class of a stop whose kept work a next Job continues

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`.

- [x] 1.1 Add `test_a_clear_keeps_the_class_of_the_stop_with_kept_work_in_implement_continued` to `tests/roadmap/test_roadmap_stop_clear.py` first: it clears the stop of an item whose record holds `implement.wip` and `implement.failure` `parser`, and asserts that `implement.continued` is `parser` and `implement.failure` is cleared. Add `test_a_clear_removes_implement_continued_without_kept_work_or_class`: for an item whose record holds `implement.continued` and no `implement.wip`, and for an item whose `implement.failure` holds no member of `FailureClass`, the record holds no `implement.continued` after the clear
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py` fails on the base
- [x] 1.2 Add `CONTINUED = "implement.continued"` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py`, and say in the docstring of the enum that the clear of a stop writes it with the class of the stop when the record holds kept work, and that the report of the next Job removes it. In `src/devops_cli/roadmap/stop_clear.py`, `_marks` takes the item: when its record holds `implement.wip` and `implement.failure` holds a member of `FailureClass`, it writes `ImplementRecordKey.CONTINUED` with that class, else it writes `ImplementRecordKey.CONTINUED: None`, and it still clears `implement.failure`; `_clear_one` passes `current`. Add the row of `implement.continued` to the job-record table of `docs/ROADMAP_WORKFLOW.md` with the text "The class of the stop whose kept work the next Job continues", and add the reader line `"implement.continued": ("text", DOCUMENT, "The class of the stop whose kept work the next Job continues")` to `READERS` in `tests/roadmap/implement/test_roadmap_implement_record_readers.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py` passes

## 2. Count the kept-work outcome of each implement Job

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/grafana/test_grafana_dashboards.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/grafana/test_grafana_dashboards.py`.

- [x] 2.1 Add these tests to `tests/roadmap/implement/test_roadmap_implement_submit.py` first, each with the job record and the fake cluster of that module, and each reading the series of `devops_cli_service_kept_work_total` by `repo`, `class` and `outcome`: `test_a_job_that_starts_from_kept_work_counts_continued_with_the_class_of_the_stop` (the record holds `implement.wip` and `implement.continued` `parser`, and the round creates the Job), `test_kept_work_that_reaches_the_ready_mark_counts_finished` (the record holds `implement.continued` `parser` and the result `ready`: `finished` and `parser` grow by 1, the record holds no `implement.continued`, `devops_cli_service_implement_jobs_total` grows by 1 only, and a second round adds nothing), `test_kept_work_that_stops_again_counts_blocked` (the report finds the new stop `oom`: `blocked` and `oom` grow by 1), `test_a_job_with_no_kept_work_adds_no_outcome` (the record holds `implement.continued` and no `implement.wip`: no kept-work series changes, the claim removes `implement.continued`, and the report adds 1 to `devops_cli_service_implement_jobs_total`) and `test_a_yield_or_a_return_of_kept_work_counts_no_outcome` (the results `yielded` and `returned` remove `implement.continued` and change no kept-work series)
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` fails on the base
- [x] 2.2 Add `CONST_SERVICE_METRIC_KEPT_WORK: Final[str] = "devops_cli_service_kept_work_total"` after `CONST_SERVICE_METRIC_IMPLEMENT_JOBS` in `src/devops_cli/config/constants.py`, with a comment that it counts the items with kept work by `repo`, failure `class` and `outcome` (#3650). Add `constants.CONST_SERVICE_METRIC_KEPT_WORK` to `deferred_metrics` of `test_cli_dashboard_service_row_reads_each_series_of_the_service` in `tests/grafana/test_grafana_dashboards.py`, and say in its docstring that #3655 also charts the kept-work counter of #3650. In `src/devops_cli/roadmap/implement/implement_submit.py`, `_create` reads `implement.continued` and `implement.wip` from the record of `target.item`. When both are set, it adds 1 to `CONST_SERVICE_METRIC_KEPT_WORK` with `repo`, that class and the outcome `continued` after `jobs.create` returns. When only `implement.continued` is set, it adds `ImplementRecordKey.CONTINUED: None` to the marks of `service_claim` and counts nothing. `_report` reads `implement.continued` from the item that it read again, and adds `ImplementRecordKey.CONTINUED: None` to the marks of `service_release`. After the release, when that mark held a class, it adds 1 with the outcome `blocked` and the class of the new stop when `_failure_of` gave one, else with `finished` and the kept class when `_attempt_result(item)` is `ready`, else nothing. `_emit_implement_metrics` does not change
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py tests/grafana/test_grafana_dashboards.py` passes

## 3. Start the kept-work label sets at zero

Kind: behavior. Reads: `src/devops_cli/server/counter_series.py`, `src/devops_cli/roadmap/failure.py`, `tests/telemetry/test_service_counter_series.py`. Changes: `src/devops_cli/server/counter_series.py`, `tests/telemetry/test_service_counter_series.py`.

- [x] 3.1 Add `test_kept_work_counter_exists_at_zero_for_each_class_and_outcome` to `tests/telemetry/test_service_counter_series.py` first: after the manager starts with `REPOS`, `CONST_SERVICE_METRIC_KEPT_WORK` has a zero series for each repository, each member of `FailureClass` and each of the outcomes `continued`, `finished` and `blocked`, and the label `outcome` holds no other value. `test_implement_jobs_counter_exists_at_zero_for_each_item_class_and_result` does not change
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [x] 3.2 In `src/devops_cli/server/counter_series.py`, `prime_service_counters` primes `CONST_SERVICE_METRIC_KEPT_WORK` with `{"repo": repo, "class": klass.value, "outcome": outcome}` for each repository, each member of `FailureClass` and each of the outcomes `continued`, `finished` and `blocked`. Say in its docstring that it primes each repository, failure class and outcome on the kept-work counter
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 4. Regenerate the telemetry reference for the new counter

Kind: other. Reads: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [x] 4.1 After the sentence of `src/devops_cli/docs/generator.py` that lists the labels of the implement jobs counter, add a sentence that the labels of `devops_cli_service_kept_work_total` are `repo`, `class` and `outcome` (#3650). Regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`, and edit no other line of it by hand
  - Verification: `$ uv run devops ci docs` passes

## 5. List the counter and its label values in the cluster README

Kind: other. Reads: `k8s/README.md`, `docs/CLUSTER.md`. Changes: `k8s/README.md`, `docs/CLUSTER.md`.

- [ ] 5.1 Add a section `## Roadmap Service metrics` at the end of `k8s/README.md` that lists `devops_cli_service_kept_work_total` with the labels `repo`, `class` and `outcome`, the outcomes `continued`, `finished` and `blocked`, and the class as a failure class of the taxonomy, and links `../docs/CLUSTER.md#roadmap-service`. In item 12 of `docs/CLUSTER.md`, add the counter with its labels and outcomes before `devops_cli_service_implement_failures_total`
  - Verification: `$ uv run devops ci docs` passes

## 6. Name the Service kept-work counter in the instruments module

Kind: other. Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`.

- [ ] 6.1 Add one sentence to the module docstring of `src/devops_cli/telemetry/instruments.py`: the series that the Service serves on its `/metrics` route, such as `devops_cli_service_kept_work_total` with the labels `repo`, `class` and `outcome`, are declared in the config constants and are no instrument of this module. Change no behavior and no other line
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## Criteria

- Group 2: A test: a next Job that starts from kept work counts `continued` with the class of the stop.
- Group 2: A test: an item with kept work that gets the ready mark counts `finished`.
- Group 2: A test: an item with kept work that stops again counts `blocked`.
- Group 2: A test: an item with no kept work does not count.
- Group 5: `k8s/README.md` lists the metric and its label values.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
