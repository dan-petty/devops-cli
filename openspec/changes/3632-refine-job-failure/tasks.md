# Tasks

## 1. A job failure is not a person wait

Kind: behavior. Reads: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_refine_job_failure.py` (new), `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_refine_investigation.py`.

- [x] 1.1 Write `tests/roadmap/test_roadmap_refine_job_failure.py` with cases for a form check failure (no person wait, a later round tries again, the record counts the tries), for the try limit (the step `failed`, no model call after it, a body edit ends it), for a question that the read tools answer, for a question that they do not answer (the failure names what they searched), for a stopped investigation, and for a question marked `(a person decides)` that still waits
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_job_failure.py` fails on the base
- [x] 1.2 Add `form_checks`, the job failure of `refine_one_item`, the record keys, the steps `retry` and `failed`, the constants and the messages, make `InvestigationTools` keep `searched`, and let `_still_waiting` and `apply_refine` read and write the new record
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_job_failure.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_refine_investigation.py` passes

## 2. The report and the inbox show a job failure

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`. Changes: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_refine_job_failure.py`.

- [x] 2.1 Add cases for the inbox line of a `failed` item (its checks, its try count, its last error, no question), for no line of a `retry` item, for the count line of the refine report, and for the explain text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_refine_job_failure.py` fails on the base
- [x] 2.2 Add the inbox class `failed`, its line, the count line of the report and the explain text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_refine_job_failure.py` passes

## 3. State the rule

Kind: documents. Reads: `docs/roadmap/refine.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/refine.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`.

- [ ] 3.1 Write the job failure, the try limit, the new record keys and the inbox class in the three documents, and regenerate the command reference with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test: a proposal that fails a form check gives no person wait, the item is due in a later round, and the job record counts the tries.
- Group 1: A test: at the try limit the item has the step `failed` and the record names the failed check.
- Group 1: A test: a `(missing verified source)` question whose answer a read tool finds does not stop the item.
- Group 1: A test: a `(missing verified source)` question that no tool answers is a job failure that lists what the tools searched.
- Group 1: A test: an investigation that stops with `Exceeded maximum output retries (2)` is a job failure and keeps no person wait.
- Group 1: A test: a question marked `(a person decides)` still makes a person wait.
- Group 2: A test: the inbox lists an item with the step `failed` as a job failure with the failed check, the try count and the last error, and lists no question for it.
- Group 2: A test: the refine report counts the items that go on without a person and lists each one.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
