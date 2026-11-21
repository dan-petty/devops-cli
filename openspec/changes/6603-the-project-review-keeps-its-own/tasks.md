# Tasks

## 1. Keep the review's own listing snapshot

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/project_review/test_review_dispatch.py`, `tests/roadmap/stores/test_listing_snapshot.py`, `tests/roadmap/project_review/test_review_openspec.py`, `tests/roadmap/stores/test_listing_shared.py`, `tests/roadmap/stores/test_roadmap_store_install.py`, `tests/roadmap/test_roadmap_run_lanes.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`, `tests/server/test_server_service.py`. Changes: `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `tests/roadmap/project_review/test_review_readers.py`.
Adds: `review_listing`, `_REVIEW_DIRNAME`, `snapshot_of`

- [ ] 1.1 `test_a_second_review_over_a_new_window_reads_only_the_gap_pages` and `test_a_stale_review_snapshot_reads_from_the_window_start`, new in `tests/roadmap/project_review/test_review_readers.py`, with `test_the_listing_reads_the_issue_after_the_watermark_once_and_keeps_the_snapshot`, `test_an_old_snapshot_of_this_schema_gives_only_the_changes_after_its_watermark` and `test_with_no_snapshot_of_this_schema_the_listing_reads_the_changes_since_the_window_start` updated to pass a review store and to assert that the intake file is byte-identical
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` fails on the base
- [ ] 1.2 Write the two tests first in `tests/roadmap/project_review/test_review_readers.py`, and update the three listing tests there to pass a review store under `tmp_path` and to assert the intake file is byte-identical. In `src/devops_cli/roadmap/stores/listing_snapshot.py`, add `_REVIEW_DIRNAME` and `review_listing`, which gives a file store under the roadmap state directory, and move the snapshot build of `IncrementalListing._keep` into `snapshot_of`. In `src/devops_cli/roadmap/project_review/readers.py`, give `_ReviewListing` the review store and the time now: read the review snapshot first, then the intake snapshot, start the gap at the later of the watermark and the window start, read from the window start when it is before the full_at of the snapshot, and save the merged records to the review store. In `src/devops_cli/roadmap/project_review/dispatch.py`, add `review_snapshots` to `ReadContext` and pass it with `now` to `read_listing`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` passes

## 2. Count the runs of each status with one request

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/project_review/data.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/project_review/test_review_catalog.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/project_review/test_review_dispatch.py`, `tests/roadmap/project_review/test_review_openspec.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_readers.py`.
Adds: `_RUN_STATUSES`

- [ ] 2.1 `test_the_runs_reader_counts_each_status_with_one_request` and `test_a_first_seven_day_review_sends_at_most_45_requests` in `tests/roadmap/project_review/test_review_readers.py`, with the two tests of the split slice in that module replaced
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` fails on the base
- [ ] 2.2 Write the two tests first in `tests/roadmap/project_review/test_review_readers.py`. In `src/devops_cli/roadmap/project_review/readers.py`, replace the page loop of `read_runs` with one request for each status of `_RUN_STATUSES`, with `per_page=1` and a status filter, plus one request with no status filter for the total, return the four counts under `statuses` with `total_count` of the total, and remove `_slice_path`, `_SECOND`, `_RUNS_KEY` and the import of the result-cap constant. In `src/devops_cli/roadmap/project_review/catalog.yaml`, give `github_runs.main_push_runs` the value program `.statuses` and a definition that names the four statuses and the total. In `src/devops_cli/roadmap/project_review/dispatch.py`, name `review_plan_each_status` for the repeat text of the runs fact. In `src/devops_cli/lang/en/messages.py`, rename `review_plan_each_slice` to `review_plan_each_status` with its new text, and delete `review_runs_at_cap`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` passes

## 3. Remove the unused runs result cap

Kind: other. Reads: `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `src/devops_cli/roadmap/project_review/readers.py`. Changes: `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [ ] 3.1 Remove `DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP` and its comment from `src/devops_cli/config/defaults.py`, remove its entry from the table of `tests/roadmap/test_roadmap_limit_classes.py`, and add its name to `REMOVED` there with the reason that the review reads no page of runs
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` passes

## 4. Describe the review snapshot and the run counts

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/project_review/readers.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 4.1 Edit the review line of `docs/ROADMAP_WORKFLOW.md` to state that the review keeps its own listing snapshot under review-listing in the roadmap state directory, reads the gap from its watermark or the window start, and reads the runs as one count for each of four statuses and one total
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: Test first: a test shows that a second review over a new window reads only the gap pages. The test fails on the base.
- Group 2: A test: a 7-day review with no intake snapshot stays at or under 45 GitHub requests.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
