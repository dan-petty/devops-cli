# Tasks

## 1. A verdict is a flag

- [x] 1.1 Change the tests of `tests/test_roadmap_intake.py` that expected a drop or a close: a possible duplicate of a not-planned issue, two candidates that duplicate each other, a candidate a person planned or one older than its original, the true duplicates of the evaluation set, a part that repeats an earlier item, a duplicate written as text, the agent candidate, the `--plan` report, the `--confirm` filing and the two #1671 cases. Each now expects a placement that names the possible original and no close. On origin/main they fail. Verify with `uv run devops ci test tests/test_roadmap_intake.py`
- [x] 1.2 Make every verdict a placement in `src/devops_cli/roadmap/intake.py`: `possible_duplicate` and `duplicate_reason` on `IntakeDecision`, the possible-duplicate line in the report and the reason comment, and the new messages in `src/devops_cli/lang/en/messages.py`. Verify with `uv run devops ci test tests/test_roadmap_intake.py`
- [x] 1.3 Delete `Outcome.DUPLICATE`, the held pairs, `_duplicate`, `_is_planned_by_person`, `_has_person_priority`, the duplicate comment and `CONST_ROADMAP_INTAKE_DUPLICATE_MARKER`, `IntakeApplied.closed`, `close_as_duplicate` in `store.py`, `github_store.py` (with its mutation, `close_as_duplicate_request`, `_require_issue_node` and the payload's `node_id`), `memory_store.py` and `request_plan.py`, the dry-run duplicate steps in `intake_requests.py`, and their messages. Delete the store tests and the fake's `closeIssue` handler that only a duplicate close used, and set up the reopened-close test with `close_by_hand`. Verify with `uv run devops ci test tests/test_roadmap_intake.py tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py`

## 2. The retry of a stopped run

- [x] 2.1 Change `test_a_retried_new_candidate_finds_the_issue_its_stopped_run_filed` to give no model verdict and expect the placement of the issue the stopped run filed. On origin/main it fails. Verify with `uv run devops ci test tests/test_roadmap_intake.py`
- [x] 2.2 Add `_new_subject`, which matches an open issue that is not finished by the candidate's title and filed body, and return its number from `intake_candidate`. Verify with `uv run devops ci test tests/test_roadmap_intake.py`

## 3. Documents

- [x] 3.1 Say in the module docstring, the help text of `devops roadmap intake`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md` and the knowledge base page on project management that intake names a possible duplicate and never drops or closes, and regenerate the documents. Verify with `uv run devops docs generate --sync-readme` and `uv run devops ci test tests/test_docs.py tests/test_fastmcp_contracts.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
