# Tasks

## 1. Keep the phases that passed and the spend of a killed Job

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/github/pr_monitor.py`, `tests/support/roadmap_implement.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_phase_marks.py` (new), `tests/invariants/test_roadmap_implement_record_keys.py` (new), `tests/support/roadmap_implement.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/github/client.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_pull.py`.

- [x] 1.1 Write the failing tests `tests/roadmap/implement/test_roadmap_implement_phase_marks.py` (checked_sha, published_sha, pr_comment_marker, spend_survives_kill, watch_progress_line, request_count, and an old-format record) and `tests/invariants/test_roadmap_implement_record_keys.py`. Let `PullFake` in `tests/support/roadmap_implement.py` answer the list and the update of the comments of the pull request
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py` fails on the base
- [ ] 1.2 Add `CHECKED_SHA` and `PUBLISHED_SHA` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py` and to its docstring. Make `comment_on_pull` in `src/devops_cli/github/client.py` return the id of the comment. Add the text of the run marker and of the progress line to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_records.py tests/invariants/test_roadmap_implement_record_keys.py`
- [ ] 1.3 In `src/devops_cli/roadmap/implement/implement_run.py`, read `implement.spend` and `implement.job` at the start of the Job (a person retry clears the spend), add the spend of the earlier Jobs to `_item_spend()` and `_spend()`, and pass `spend` to `_record` in `_groups`. Clear `implement.spend`, `implement.checked_sha` and `implement.published_sha` in `_return_to_new`, and the two phase marks in `_ready`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py -k "spend_survives_kill or return_to_new or older_version"`
- [ ] 1.4 In `_push`, skip the scoped checks when `implement.checked_sha` equals the head and write it after they pass. Skip the push when `implement.published_sha` equals the head and write it after the push or the publish
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py -k "checked_sha or published_sha or phase_marks"`
- [ ] 1.5 Write the comment of the job with the run marker: list the comments once, update the comment with the marker, post it when none exists, and write nothing when the Job has nothing to show. Remove the parameter `since` of `_comment` and `last_comment_mark`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py -k "pr_comment_marker or request_count"`
- [ ] 1.6 Give `watch_pull` in `src/devops_cli/roadmap/implement/implement_pull.py` a `status_callback` that writes one progress line at each poll after the first with a check that runs
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py -k watch_progress_line`
- [ ] 1.7 Amend the tests of `tests/roadmap/implement/` and `tests/core/` that count the comments of the pull request or the record after a run, so that they hold the comment with the run marker and the new marks
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/core/test_roadmap_implement_checks.py tests/core/test_roadmap_implement_planned_run.py`

## 2. State the marks and the comment in the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [ ] 2.1 In `docs/ROADMAP_WORKFLOW.md`, add the rows of `implement.checked_sha` and `implement.published_sha` to the table of the record keys, and change the row of `implement.spend` to say that it is the sum of the Jobs of the item and that a retry of a person clears it
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`
- [ ] 2.2 In `docs/roadmap/implement.md`, state that a Job skips the scoped checks and the push at a head that its marks hold, that the comment on the pull request has one comment for each run with a run marker, and that the wait for the checks writes a progress line
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: A second Job at a head that `implement.checked_sha` records SHALL run no scoped check, and a head that differs SHALL run them.
- Group 1: The Job SHALL write `implement.published_sha` after the push, and a second Job at that head SHALL push nothing.
- Group 1: The comment on the pull request SHALL have the marker line of the run, a rerun with no new outcome SHALL post no comment with the body `-`, and a repair round SHALL update the comment of the run.
- Group 1: The group mark SHALL carry the spend, a continuation SHALL start its item budget from the recorded spend, and a stop or ready SHALL write the sum.
- Group 1: A retry of a person SHALL start from zero spend, and a return to New SHALL clear the spend.
- Group 1: The watch of the checks SHALL write one progress line at each poll interval after the first.
- Group 1: The Job SHALL send at most 5 extra requests for the comment marker and the two phase marks.
- Group 1: A record of an older version SHALL load, and each key of the record SHALL have a reader or a spec line in a test.
- Group 2: The documents SHALL name the two keys, the sum of the spend, the run marker and the progress line.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
