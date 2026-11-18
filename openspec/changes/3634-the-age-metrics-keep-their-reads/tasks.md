# Tasks

## 1. Add the record of the item label times

Kind: behavior. Reads: `src/devops_cli/output/file_writer.py`, `src/devops_cli/roadmap/stores/store.py`. Changes: `src/devops_cli/github/item_label_times.py` (new), `tests/github/test_item_label_times.py` (new).

- [x] 1.1 Write `test_the_record_round_trips_through_its_file` and `test_a_record_that_cannot_be_written_logs_one_error` in `tests/github/test_item_label_times.py` first. The first keeps one Item's updated_at and label times with `keep_item_label_times` and asserts that `read_item_label_times` gives them back, and that a missing file reads as an empty record. The second points the writer at a path under a file and asserts one error log line and no raise
  - Verification: `$ uv run devops ci test tests/github/test_item_label_times.py` fails on the base
- [x] 1.2 Create `src/devops_cli/github/item_label_times.py` with the model `KeptItemLabelTimes` (the `updated_at` and the label times of one Item), the model `ItemLabelTimesRecord`, the constant `ITEM_LABEL_TIMES_FILE`, and the functions `item_label_times_path(repo_dir)`, `read_item_label_times(path)` and `keep_item_label_times(path, record)`. Write the file with `write_json_file` of `src/devops_cli/output/file_writer.py` and `atomic=True`, and log one error line that names the file when the write fails. The module docstring names item-label-times.json and the cap of 20 label-event reads a round
  - Verification: `$ uv run devops ci test tests/github/test_item_label_times.py` passes

## 2. Key the label times by updated_at and cap the reads

Kind: behavior. Reads: `src/devops_cli/github/metrics.py`, `src/devops_cli/github/item_label_times.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py`, `tests/conftest.py`. Changes: `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py`, `tests/conftest.py`.

- [x] 2.1 Write `test_a_new_process_reads_no_label_events_of_an_item_the_record_holds`, `test_a_round_reads_the_label_events_of_at_most_20_items`, `test_a_deferred_item_is_read_before_a_new_one`, `test_a_round_keeps_the_entry_of_an_item_it_deferred` and `test_a_closed_item_leaves_the_record` in `tests/github/test_github_metrics.py`, and rename `test_a_round_reads_an_items_label_events_only_when_its_status_or_owner_changes` to `test_a_round_reads_an_items_label_events_only_when_its_updated_at_moves`, with the clock moved before the field write. Give `test_a_round_of_one_repository_keeps_the_label_times_of_another` one record path for each repository, and give `_warm_ages` and `_counted_round` of `tests/github/test_github_metrics_request_budget.py` one record path under `tmp_path`, so the 5-request budget test passes with the process dict gone
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/github/test_github_metrics_request_budget.py` fails on the base
- [x] 2.2 In `src/devops_cli/github/metrics.py`, delete `_item_label_times`, `reset_item_age_cache` and their `__all__` entries, add `_MAX_ITEM_AGE_READS_PER_ROUND: Final[int] = 20`, and give `_label_times` the kept record and the cap: an Item whose entry holds the current `updated_at` reuses its times, an Item whose `updated_at` moved is read before an Item that the record does not hold, at most 20 Items are read, an Item that the round does not read keeps the times its entry holds, and the record keeps the entry of every open Item and drops the Items that left the open list. Give `_read_item_ages`, `get_item_age_metrics` and `collect_project_metrics_report` the keyword `label_times_record: Path | None = None`, load the record once, pass it from the collection through `_read_item_ages` to `get_item_age_metrics`, write it with `keep_item_label_times`, and guard the claim age with `times.get(item.number, {})`. A round with no path reads every Item and writes no record. Drop `reset_item_age_cache` from the reset map in `tests/conftest.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/github/test_github_metrics_request_budget.py` passes

## 3. Measure the requests of one new pod

Kind: other. Reads: `tests/github/test_github_metrics_request_budget.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/github/item_label_times.py`. Changes: `tests/github/test_github_metrics_request_budget.py`.

- [x] 3.1 Add `test_a_new_pod_sends_25_requests_in_its_first_round` to `tests/github/test_github_metrics_request_budget.py`: seed 30 open Items, run one counted round with a record path whose file does not exist, and assert 25, the 5 fixed reads of `METRICS_ROW_GITHUB_REQUEST_BUDGET` plus the 20 label-event reads of the cap. The pull request body states that number
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics_request_budget.py` passes

## 4. Keep the record in the state directory of the row

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/github/item_label_times.py`, `tests/roadmap/test_roadmap_run_metrics.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run_metrics.py`.

- [x] 4.1 Write `test_the_metrics_row_keeps_the_label_times_in_the_state_directory_of_its_repository` in `tests/roadmap/test_roadmap_run_metrics.py` first: two rounds of the metrics row with the same repo_dir read the label events of an Item once, the second round still sends its age, and item-label-times.json sits in that directory
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_metrics.py` fails on the base
- [x] 4.2 In `src/devops_cli/roadmap/run.py`, name the keyword `repo_dir: Path | None = None` of `_run_metrics_adapter` before `**_: Any`, pass `label_times_record=item_label_times_path(repo_dir) if repo_dir is not None else None` to `collect_project_metrics_report`, and say in its docstring that the row keeps the label times of each open Item in item-label-times.json of its repository and reads the label events of at most 20 Items a round
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_metrics.py` passes

## 5. Name the record file in the cluster document

Kind: other. Reads: `docs/CLUSTER.md`, `src/devops_cli/github/item_label_times.py`. Changes: `docs/CLUSTER.md`.

- [ ] 5.1 In item 11 of `docs/CLUSTER.md`, add item-label-times.json to the directory of each repository beside its schedule.json: the metrics row writes the `updated_at` and the label times of each open Item there, keeps the entry of an Item that the cap defers, drops an Item that closes, and reads the label events of at most 20 Items a round
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/CLUSTER.md` item 11 to name item-label-times.json beside schedule.json in the directory of each repository, with the `updated_at` it holds, the kept entry of a deferred Item and the cap of 20 label-event reads a round
  - Verification: `$ uv run devops ci docs` passes

## 6. State the live level of the metrics row

Kind: other. Reads: `docs/CLUSTER.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `docs/CLUSTER.md`.

- [ ] 6.1 In item 12 of `docs/CLUSTER.md`, add the live check of the metrics row: the query sum by (row)(increase(devops_cli_github_requests_total{job="roadmap-service", row="metrics", status!="304"}[1h])), the band of 222 to 305 requests an hour of a repository before #3601, and the note that a rollout adds no full read of the open Items because the row keeps their label times in item-label-times.json. The counter is defined in `src/devops_cli/telemetry/instruments.py` and stays as it is: the change adds no series, no label and no query, and run this check by hand: Deploy the merged image to the Service and read the query of item 12 in Grafana Explore. Roll the roadmap-service deployment once, wait an hour and read the value, then roll it again, wait an hour and read the value again. Compare each value with the band of 222 to 305 requests an hour, and post the two readings with their times on #3634.
- [ ] 6.2 Edit `docs/CLUSTER.md` item 12 to give the metrics row's live check, its band before #3601 and why a rollout adds no full read
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: Measure the requests of the metrics row for one new pod, and state the number in the pull request.
- Group 2: A test: a new process does not read the events of an item whose `updated_at` it already holds in the kept record.
- Group 2: A test: the row reads events for at most a fixed number of items in a round, and the rest wait for later rounds.
- Group 6: Run live: the metrics row stays near its level before #3601 over a period with two rollouts.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
