# Tasks

## 1. The store gives comment times and the last change of a path

- [x] 1.1 Write `test_a_comment_is_kept_on_its_issue_with_the_time_it_was_made` and `test_a_path_changed_when_the_newest_commit_that_changed_it_was_made` in `tests/test_roadmap_store_contract.py`, and `test_comments_on_reads_every_comment_of_the_issue_oldest_first_with_its_time`, `test_path_changed_at_reads_the_newest_commit_of_a_path_once_for_the_stores_life` and `test_a_failed_read_of_the_commits_of_a_path_raises` in `tests/test_roadmap_github_store.py`, and verify that `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py` fails on the base
- [x] 1.2 Add `IssueComment` and `RoadmapStore.path_changed_at` to `src/devops_cli/roadmap/store.py`, implement them in `github_store.py` (`path_commits_args`) and `memory_store.py` (`seed_commit`), read the comment body in `intake.py`, give the fake's comments a time in `tests/roadmap_board_fake.py`, and verify that `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py tests/test_roadmap_intake.py tests/test_roadmap_return.py` passes

## 2. Refine records the cited paths and ends a wait when they change

- [x] 2.1 Write `test_a_waiting_item_whose_cited_path_changes_on_main_after_refines_comment_is_refined_again`, `test_a_waiting_item_whose_cited_path_does_not_change_keeps_waiting_with_no_model_call`, `test_refine_records_each_cited_path_the_checkout_holds_once_and_names_them_in_its_comment` and `test_a_proposal_that_names_no_block_records_no_cited_path` in `tests/test_roadmap_refine.py`, and verify that `uv run devops ci test tests/test_roadmap_refine.py -k "cited_path or no_block"` fails on the base
- [x] 2.2 Add `block_paths` to `RefinementProposal` and to the proposal prompt, keep the checkout's paths in `validate_proposal`, record them as `refine.block_paths` in `apply_refine`, name them in the next-step comment, end the wait in `_still_waiting` when a recorded path changed at or after refine's last comment, and verify that `uv run devops ci test tests/test_roadmap_refine.py` passes
- [x] 2.3 Give the new end of a wait in the help text of `devops roadmap refine` and in the docstrings of `refine.py`, `store.py`, `github_store.py` and `memory_store.py`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 3. The dry-run plan counts the commit reads

- [x] 3.1 Write `test_a_refine_round_plans_a_read_of_each_cited_path_and_an_item_plan_none` in `tests/test_roadmap_dry_runs.py`, and verify that `uv run devops ci test tests/test_roadmap_dry_runs.py -k cited_path` fails on the base
- [x] 3.2 Add the commit read of each cited path to the round's plan in `refine_requests` (`StoreRequests.path_change`), and verify that `uv run devops ci test tests/test_roadmap_dry_runs.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
