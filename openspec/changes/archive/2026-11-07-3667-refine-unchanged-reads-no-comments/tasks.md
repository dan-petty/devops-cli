# Tasks

## 1. The issue listing gives the count of comments

Kind: behavior

- [x] 1.1 Write `test_an_item_carries_the_count_of_comments_on_its_issue` in `tests/roadmap/test_roadmap_store_contract.py`, and give the GitHub fake and the in-memory store the count
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py`
- [x] 1.2 Add `comments` to `IssueRecord`, `Item` and the issue payload of `github_store.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_github_store.py`

## 2. A round reads no comment of an unchanged waiting item

Kind: behavior

- [x] 2.1 Write the tests of the section "An item nothing changed costs no comment read" in `tests/roadmap/test_roadmap_refine.py` and `test_a_refine_round_plans_the_record_of_the_comments_it_read_of_a_waiting_item` in `tests/roadmap/test_roadmap_dry_runs.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`
- [x] 2.2 Add `COMMENTS_SEEN`, `COMMENTED_AT` and `WAIT_REFS` to `RefineRecordKey`, end the wait in `_still_waiting` from the record when the count holds, record the marks in apply, and list the record in the dry-run plan
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_dry_runs.py`

## 3. The documents state the new cost

Kind: other

- [x] 3.1 State the new cost in the docstring of `src/devops_cli/roadmap/refine.py` and in the docstrings of `store.py` and `request_plan.py`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

## Workflow follow-up

- The measure of the drop of GitHub requests is the work of #3866.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
