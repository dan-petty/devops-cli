# Tasks

## 1. Compare the answer of an issue request with the request

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/github/repo_ref.py`, `tests/support/roadmap_github_store.py`, `tests/fixtures/roadmap/issues-open.json`. Changes: `src/devops_cli/roadmap/stores/github_store.py`, `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py`, `tests/roadmap/stores/test_github_store_brain.py`.
Adds: `_IssuePayload.repository`, `GitHubRoadmapStore._read_issue`, `GitHubRoadmapStore._answered`, `GitHubRoadmapStore._is_requested`

- [x] 1.1 Add `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py` with the failing cases of a read and of a write: `test_an_answer_that_names_another_issue_reads_as_no_issue`, `test_the_body_read_refuses_an_answer_that_names_another_issue`, `test_the_title_read_of_a_pull_request_takes_no_answer_that_names_another_one`, `test_the_refusal_logs_a_warning_that_names_the_requested_number_only`, `test_a_write_sends_no_request_when_the_read_answers_with_another_issue` and `test_a_write_whose_answer_names_another_issue_is_refused_and_not_kept`, and with `test_an_answer_that_names_the_requested_issue_reads_as_before`, which passes on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_answer.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stores/github_store.py`, give `_IssuePayload` the field `url` and the property `repository`, add `_read_issue`, `_answered` and `_is_requested`, and read through them in `issue`, `_revalidate_issue`, `_require_issue`, `pull_title` and `_send_edit`. Give the 3 answers of `tests/roadmap/stores/test_github_store_brain.py` that named another repository than their store the URLs of their store
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_answer.py tests/roadmap/stores/test_github_store_brain.py` passes

## 2. Drop the record of a number that is no issue of the repository

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/valkey/tiered.py`. Changes: `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/project_review/readers.py`, `tests/support/fakes/github_repository.py`, `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py`, `tests/roadmap/test_roadmap_rows_issue_answer.py`.
Adds: `forget_issue`, `IncrementalListing.drop`, `ListingRead.drop`, `GitHubRoadmapStore._gone`, `GitHubFake.move_issue`

- [x] 2.1 Add `GitHubFake.move_issue` to `tests/support/fakes/github_repository.py`. Add the failing cases of the listing and of the brain to `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py` (`test_a_round_drops_the_record_of_an_issue_whose_read_answers_with_another_issue`, `test_a_dropped_record_stays_out_when_another_copy_of_the_snapshot_holds_it`, `test_a_missing_issue_that_the_listing_holds_leaves_the_listing`, `test_a_conditional_read_that_answers_with_another_issue_gives_no_issue_and_drops_the_entry`, `test_an_entry_that_names_another_issue_is_not_used_and_is_removed`), and the failing cases of the rows to `tests/roadmap/test_roadmap_rows_issue_answer.py` (`test_an_alternatives_round_sends_no_write_for_an_item_whose_read_answers_with_another_issue`, `test_a_status_sweep_sends_no_write_for_an_item_whose_read_answers_with_another_issue`)
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_answer.py tests/roadmap/test_roadmap_rows_issue_answer.py` fails on the base
- [x] 2.2 Add `forget_issue` to `src/devops_cli/roadmap/stores/brain_issues.py`, and `drop` to `ListingRead`, `IncrementalListing` and the review listing. Make `IncrementalListing.read` leave out the numbers that `drop` named, until GitHub lists them or the read is a full one. In `github_store.py`, add `_gone`, call it for a refused answer and for a 404 answer, and make `_cached_issue` use an entry only when its record names the requested number and the repository of the store
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_issue_answer.py tests/roadmap/test_roadmap_rows_issue_answer.py tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/stores/test_listing_shared.py tests/roadmap/stores/test_brain_issues.py` passes

## 3. Give the rule in the cluster document

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`.

- [x] 3.1 In the paragraph of `docs/CLUSTER.md` about the issue cache, say what the store does with an answer and with an entry that name another issue
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: Test first: `issue`, `item`, `read_issue_body` and each write that reads the issue first give no record, and send no write, for an answer with another number or another repository. The tests fail on the base.
- Group 2: A test: a listing round drops the record of a number whose read answers for another issue, and no row selects it again.
- Group 1: A test: an answer for the requested number and repository reads as today.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
