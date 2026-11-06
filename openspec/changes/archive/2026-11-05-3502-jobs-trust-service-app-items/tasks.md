# Tasks

## 1. The author login in the store

Kind: behavior. Reads: `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap_github_fake.py`.

- [x] 1.1 Write `test_an_item_carries_its_authors_login` and `test_a_comment_carries_its_authors_login_and_association`, and give the fake GitHub and the contract world an `author_login`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py`
- [x] 1.2 Add `author_login` to `Item`, `IssueRecord` and `IssueComment`, read `user.login` in the GitHub store, and let the in-memory store seed it.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_intake.py`

## 2. The trust rule and the four readers

Kind: behavior. Reads: `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_trust.py`, `tests/roadmap/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_refine.py`.

- [x] 2.1 Write the tests of the rule, of its lookalike and no-slug cases, of the approval, and of each reader, and the test that an `implement: retry` comment of the App starts no retry.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_trust.py tests/roadmap/test_roadmap_implement_selection.py`
- [x] 2.2 Add `trust.py` and the record key `refine.judge`, and make the four readers use the rule, with the reasons that name the author and the missing approval.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_trust.py tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_refine.py`

## 3. Refine reviews the items of a bot, tells the other authors and reads trusted replies

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_verify.py`. Changes: `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_refine_trust.py`.

- [x] 3.1 Write the tests of the review (approval, refusal, second round, body edit, item of the owner, unchanged approval), of the comment to the author, and of the replies.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_trust.py`
- [x] 3.2 Add `refine_judge.py`, the verdict in `RefinedItem` and in the marks, the `edit` step comment, the notice of `WaitingItem`, and the filter of the comments.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_trust.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_refine_deferred.py tests/roadmap/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_stage_verify.py`

## 4. The approval holds for the body that the review read

Kind: behavior. Reads: `src/devops_cli/roadmap/refine.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_trust.py`, `tests/roadmap/test_roadmap_trust.py`, `tests/roadmap/test_roadmap_refine_trust.py`, `tests/roadmap/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_repair.py`, `tests/roadmap/test_roadmap_explain.py`.

- [x] 4.1 Write the tests of the three readers that leave out an approved bot item with an edited body. Add the tests of the second round and of the verdict that a record of the hashes clears.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_trust.py tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_refine_trust.py`
- [x] 4.2 Move the section split, the hashes and the unchanged check to `body_hash.py`, and make `is_approved` read them. Make `_refinable` take a Ready item of a bot with no valid approval. Clear the verdict where a round records the hashes with no review.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_trust.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_refine_trust.py tests/roadmap/test_roadmap_repair.py tests/roadmap/test_roadmap_explain.py`

## 5. Replies and the dry-run plan

Kind: behavior. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 5.1 Write `test_the_request_holds_no_comment_of_an_account_that_the_jobs_do_not_trust` and the dry-run test of the read and the notice. Then filter the comments of the alternatives job with `trusted_replies`. Add the two requests and their conditions to `refine_requests`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_dry_runs.py`

## 6. Documents

Kind: documents. Changes: `SECURITY.md`, `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `docs/ROADMAP_WORKFLOW.md`, and the deltas of `roadmap-alternatives`, `roadmap-stage` and `roadmap-implement-job` in this change.

- [x] 6.1 State the trust rule, the approval and their reason in `SECURITY.md`. State the review and its record key in `docs/roadmap/refine.md` and `docs/ROADMAP_WORKFLOW.md`. State the items that the check takes in `docs/roadmap/alternatives.md`, and the new rule in the specs of the jobs.
  - Verification: `uv run devops ci docs`

## 7. Archive

Kind: documents.

- [x] 7.1 Archive the change with `uv run devops openspec archive 3502-jobs-trust-service-app-items`.

## Workflow follow-up

- Pending a person: decide at merge. The change widens the trust rule of #2478 to the Service App's bot and `github-actions[bot]`, and AGENTS.md rule 5 reserves that decision to the owner. The owner recorded the decision on #3502 on 2026-11-05.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
