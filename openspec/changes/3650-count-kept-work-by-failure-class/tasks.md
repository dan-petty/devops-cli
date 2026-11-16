# Tasks

## 1. Keep the class of a stop whose kept work a next Job continues

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`.

- [ ] 1.1 Add `test_a_clear_keeps_the_class_of_the_stop_with_kept_work_in_implement_continued` to `tests/roadmap/test_roadmap_stop_clear.py` first: it clears the stop of an item whose record holds `implement.wip` and `implement.failure` `parser`, and asserts that `implement.continued` is `parser` and `implement.failure` is cleared. Add `test_a_clear_writes_no_continued_class_without_kept_work` for an item whose record holds no `implement.wip`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py` fails on the base
- [ ] 1.2 Add `CONTINUED = "implement.continued"` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py`, and say in the docstring of the enum that it holds the class of the stop whose kept work a next Job continues. In `src/devops_cli/roadmap/stop_clear.py`, `_marks` takes the item: when its record holds `implement.wip` it writes `CONTINUED` with the class of `implement.failure`, or `none` when the record holds no class, and it still clears `implement.failure`; `_clear_one` passes the item it writes. Add the row of `implement.continued` to the job-record table of `docs/ROADMAP_WORKFLOW.md`, and add the reader line `("text", DOCUMENT, "The class of the stop whose kept work the next Job continues")` to the `READERS` table of `tests/roadmap/implement/test_roadmap_implement_record_readers.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 1.3 Edit `docs/ROADMAP_WORKFLOW.md` with the row of `implement.continued` in the job-record table
  - Verification: `$ uv run devops ci docs` passes

## 2. Count the kept-work outcome of each implement Job

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`. Changes: `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`.

- [ ] 2.1 Add `test_a_job_that_starts_from_kept_work_counts_continued_with_the_class_of_the_stop`, `test_kept_work_that_reaches_the_ready_mark_counts_finished`, `test_kept_work_that_stops_again_counts_blocked` and `test_a_job_with_no_kept_work_adds_no_outcome` to `tests/roadmap/implement/test_roadmap_implement_submit.py` first, each building the job record and the fake cluster of that module and reading the series of `devops_cli_service_implement_jobs_total`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` fails on the base
- [ ] 2.2 In `src/devops_cli/roadmap/implement/implement_submit.py`, `_create` reads `implement.continued` from `target.item` and, after `jobs.create` returns, adds 1 to `CONST_SERVICE_METRIC_IMPLEMENT_JOBS` with `repo`, the item class, the result `continued` and that class. `_report` reads `implement.continued` before it writes the marks, adds `CONTINUED: None` to the `service_release` marks, and after the release adds 1 with the result `finished` when `_attempt_result(item)` is `ready`, or with the result `blocked` and the class of the new stop when `_failure_of` gives one. `_emit_implement_metrics` puts the label `class` on every increment of that counter, with the failure class it counts or `none`, so a report with no kept work still adds the one increment of the base requirement
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` passes

## 3. Start the kept-work label sets at zero

Kind: behavior. Reads: `src/devops_cli/server/counter_series.py`, `src/devops_cli/roadmap/failure.py`, `tests/telemetry/test_service_counter_series.py`. Changes: `src/devops_cli/server/counter_series.py`, `tests/telemetry/test_service_counter_series.py`.

- [ ] 3.1 Update `test_implement_jobs_counter_exists_at_zero_for_each_item_class_and_result` in `tests/telemetry/test_service_counter_series.py` to expect the label `class`, and add `test_implement_jobs_counter_starts_the_kept_work_series_at_zero` to that module
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [ ] 3.2 In `src/devops_cli/server/counter_series.py`, prime `CONST_SERVICE_METRIC_IMPLEMENT_JOBS` with the label `class`: `none` and each member of `FailureClass` for the result `failed`, `none` for the results `succeeded` and `gone`, and `none` and each member of `FailureClass` for the results `continued`, `finished` and `blocked`. Say in the docstring of `prime_service_counters` that the jobs counter primes the class of each result
  - Verification: `$ uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 4. Regenerate the telemetry reference for the new label

Kind: other. Reads: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [ ] 4.1 Change the sentence of `src/devops_cli/docs/generator.py` that lists the labels of the implement jobs counter so that it names `repo`, `item_class`, `result` and `class`, and says that `class` is the failure class that an increment counts, or `none`. Regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`, and edit no other line of it by hand
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `src/devops_cli/docs/generator.py` and regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 5. List the counter and its label values in the cluster README

Kind: other. Reads: `k8s/README.md`, `docs/CLUSTER.md`. Changes: `k8s/README.md`, `docs/CLUSTER.md`.

- [ ] 5.1 Add a section `## Roadmap Service metrics` at the end of `k8s/README.md` that lists `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class`, `result` and `class`, the results `succeeded`, `failed`, `gone`, `continued`, `finished` and `blocked`, and the class `none` or a failure class, and links `docs/CLUSTER.md#roadmap-service`. Extend the sentence of `docs/CLUSTER.md` that describes that counter with the label `class` and the kept-work results
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `k8s/README.md` and `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs` passes

## 6. Name the Service implement counter in the instruments module

Kind: other. Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`.

- [ ] 6.1 Add one sentence to the module docstring of `src/devops_cli/telemetry/instruments.py`: the series that the Service serves on its `/metrics` route, such as `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class`, `result` and `class`, are declared in the config constants and are no instrument of this module. Change no behavior and no other line
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes
- [ ] 6.2 Edit the module docstring of `src/devops_cli/telemetry/instruments.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test: a next Job that starts from kept work counts `continued` with the class of the stop.
- Group 2: A test: an item with kept work that gets the ready mark counts `finished`.
- Group 2: A test: an item with kept work that stops again counts `blocked`.
- Group 2: A test: an item with no kept work does not count.
- Group 5: `k8s/README.md` lists the metric and its label values.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
