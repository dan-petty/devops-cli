# Tasks

## 1. Keep the review's own listing snapshot

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/project_review/test_review_dispatch.py`, `tests/roadmap/stores/test_listing_snapshot.py`, `tests/roadmap/project_review/test_review_openspec.py`, `tests/roadmap/stores/test_listing_shared.py`, `tests/roadmap/stores/test_roadmap_store_install.py`, `tests/roadmap/test_roadmap_run_lanes.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`, `tests/server/test_server_service.py`. Changes: `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `tests/roadmap/project_review/test_review_readers.py`.
Adds: `review_listing`, `_REVIEW_DIRNAME`, `snapshot_of`

- [x] 1.1 `test_a_second_review_over_a_new_window_reads_only_the_gap_pages`, `test_a_stale_review_snapshot_reads_from_the_window_start` and `test_a_wider_review_reads_a_change_between_the_watermark_and_a_later_window_start`, new in `tests/roadmap/project_review/test_review_readers.py`, with `test_the_listing_reads_the_issue_after_the_watermark_once_and_keeps_the_snapshot`, `test_an_old_snapshot_of_this_schema_gives_only_the_changes_after_its_watermark` and `test_with_no_snapshot_of_this_schema_the_listing_reads_the_changes_since_the_window_start` updated to pass a review store and to assert that the intake file is byte-identical
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` fails on the base
- [x] 1.2 Write the three new tests of 1.1 first in `tests/roadmap/project_review/test_review_readers.py`, and update the three listing tests of 1.1 to pass a review store under `tmp_path` and to assert the intake file is byte-identical. In `src/devops_cli/roadmap/stores/listing_snapshot.py`, add `_REVIEW_DIRNAME` and `review_listing`, which gives a file store under the roadmap state directory, and move the snapshot build of `IncrementalListing._keep` into `snapshot_of`. In `src/devops_cli/roadmap/project_review/readers.py`, give `_ReviewListing` the review store and the time now: read the review snapshot first, then the intake snapshot, start the gap at the later of the watermark and the window start, read from the window start when it is before the full_at of the snapshot, save the gap start as the full_at when the gap starts after the watermark, and save the merged records to the review store. In `src/devops_cli/roadmap/project_review/dispatch.py`, add `review_snapshots` to `ReadContext` and pass it with `now` to `read_listing`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` passes

## 2. Count the runs of each status with one request

Kind: behavior. Reads: `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/project_review/data.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/project_review/test_review_catalog.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/project_review/test_review_dispatch.py`, `tests/roadmap/project_review/test_review_openspec.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/project_review/test_review_readers.py`.
Adds: `_RUN_STATUSES`, `review_runs_above_total`, `review_runs_no_count`

- [x] 2.1 `test_a_window_under_the_cap_reads_its_total_then_one_count_for_each_status`, `test_a_window_above_the_cap_splits_in_halves_whose_counts_add_up`, `test_a_slice_of_one_second_at_the_cap_raises`, `test_status_counts_above_the_total_of_a_slice_raise`, `test_a_run_in_the_start_second_counts_in_the_window_before_and_not_in_this_one`, `test_a_skipped_run_is_in_the_total_and_in_no_status_count`, `test_a_runs_page_with_no_count_raises`, `test_the_main_push_runs_fact_gives_the_four_counts_and_the_total_of_the_window`, `test_the_runs_fact_of_a_page_with_no_count_gives_an_error` and `test_a_first_seven_day_review_sends_at_most_45_requests` in `tests/roadmap/project_review/test_review_readers.py`, with a fake that stops each filtered `total_count` at 2,500, as GitHub does
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` fails on the base
- [x] 2.2 Write the ten tests of 2.1 first in `tests/roadmap/project_review/test_review_readers.py`. In `src/devops_cli/roadmap/project_review/readers.py`, replace the page loop of `read_runs` with requests of one entry (`per_page=1`) for each created slice after the start second up to the end: the total first, a split in two halves while the total reaches `CONST_ROADMAP_REVIEW_RUN_COUNT_CAP`, then one request for each status of `_RUN_STATUSES` with a status filter; add the counts of the slices, return the four counts under `statuses` with `total_count` of the totals, raise `RoadmapReviewError` for a page with no total, a one-second slice at the cap and status counts above a total, and remove `_slice_path`, `_RUNS_KEY` and the import of the page-cap constant. In `src/devops_cli/roadmap/project_review/catalog.yaml`, give `github_runs.main_push_runs` the value program `.statuses` and a definition that names the four statuses and the total. In `src/devops_cli/lang/en/messages.py`, give `review_plan_each_slice` the text of the count slices, give `review_runs_at_cap` the count cap, and add `review_runs_above_total` and `review_runs_no_count`
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_readers.py` passes

## 3. Replace the runs page cap with the count cap

Kind: other. Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `src/devops_cli/roadmap/project_review/readers.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 3.1 Remove `DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP` and its comment from `src/devops_cli/config/defaults.py`, remove its entry from the table of `tests/roadmap/test_roadmap_limit_classes.py`, and add its name to `REMOVED` there with the reason that the review reads no page of runs. Add `CONST_ROADMAP_REVIEW_RUN_COUNT_CAP`, 2,500, to `src/devops_cli/config/constants.py` with the class kept in that table
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` passes

## 4. Describe the review snapshot and the run counts

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/project_review/readers.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 4.1 Edit the review line of `docs/ROADMAP_WORKFLOW.md` to state that the review keeps its own listing snapshot under review-listing in the roadmap state directory, reads the gap from its watermark or the window start, and reads the runs as the total and one count for each of four statuses of each created slice under the count cap of 2,500
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: Test first: a test shows that a second review over a new window reads only the gap pages. The test fails on the base.
- Group 2: A test: a 7-day review with no intake snapshot stays at or under 45 GitHub requests.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
