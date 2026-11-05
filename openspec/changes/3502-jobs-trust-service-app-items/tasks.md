# Tasks

## 1. The author login in the store

Kind: behavior. Reads: `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap_github_fake.py`.

- [x] 1.1 Write `test_an_item_carries_its_authors_login` and `test_a_comment_carries_its_authors_login_and_association`, and give the fake GitHub and the contract world an `author_login`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py`
- [x] 1.2 Add `author_login` to `Item`, `IssueRecord` and `IssueComment`, read `user.login` in the GitHub store, and let the in-memory store seed it.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_intake.py`

## 2. The trust rule and the four readers

Kind: behavior. Reads: `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_trust.py`, `tests/roadmap/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_refine.py`.

- [ ] 2.1 Write the tests of the rule, of its lookalike and no-slug cases, of the approval, and of each reader, and the test that an `implement: retry` comment of the App starts no retry.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_trust.py tests/roadmap/test_roadmap_implement_selection.py`
- [ ] 2.2 Add `trust.py` and the record key `refine.judge`, and make the four readers use the rule, with the reasons that name the author and the missing approval.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_trust.py tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_stage_selection.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_refine.py`

## 3. Refine reviews the items of a bot, tells the other authors and reads trusted replies

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_verify.py`. Changes: `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_refine_trust.py`.

- [ ] 3.1 Write the tests of the review (approval, refusal, second round, body edit, item of the owner, unchanged approval), of the comment to the author, and of the replies.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_trust.py`
- [ ] 3.2 Add `refine_judge.py`, the verdict in `RefinedItem` and in the marks, the `edit` step comment, the notice of `WaitingItem`, and the filter of the comments.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_trust.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_refine_deferred.py tests/roadmap/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_stage_verify.py`

## 4. Documents

Kind: documents. Changes: `SECURITY.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 4.1 State the trust rule and its reason in `SECURITY.md`, the review and its record key in `docs/roadmap/refine.md` and `docs/ROADMAP_WORKFLOW.md`.
  - Verification: `uv run devops ci docs`

## 5. Archive

Kind: documents.

- [ ] 5.1 Archive the change with `uv run devops openspec archive 3502-jobs-trust-service-app-items`.

## Workflow follow-up

- Pending a person: decide at merge. The change widens the trust rule of #2478 to the Service App's bot and `github-actions[bot]`, and AGENTS.md rule 5 reserves that decision to the owner. The owner recorded the decision on #3502 on 2026-11-05.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
