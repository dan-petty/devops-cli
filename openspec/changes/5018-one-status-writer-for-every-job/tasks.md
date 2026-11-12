# Tasks

## 1. One Status writer

Kind: behavior. Reads: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stores/store.py`. Changes: `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_status_sync.py`.

- [x] 1.1 Write the tests first in `tests/roadmap/test_roadmap_status_sync.py`: no write and no read when the label is equal; one write and one read-back on a difference; no request in a dry run; the marks alone when the label is equal; a lost write raises `RoadmapStatusLostError`; New, In Review and In Progress from the new facts
  - Verification: `$ uv run pytest tests/roadmap -k status_writer`
- [x] 1.2 Add `write_status`, `StatusWrite`, the facts `needs_refine`, `pull_ready` and `pull_open`, and `RoadmapStatusLostError`, and make `sync_status` call `write_status`
  - Verification: `$ uv run pytest tests/roadmap -k status_writer`

## 2. Every caller uses the writer

Kind: behavior. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/intake/intake_requests.py`, `src/devops_cli/roadmap/return_item.py`, `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/invariants/test_architectural_invariants.py`.

- [x] 2.1 Write the structural test first in `tests/invariants/test_architectural_invariants.py`: a `set_field` of `ItemField.STATUS` or a label write of a `status/` label outside `status_sync.py` and the stores fails with its file and line
  - Verification: `$ uv run pytest tests/invariants/test_architectural_invariants.py -k status_writer`
- [x] 2.2 Add the store read `issue(number)`, Item or not, with a case of the store contract, and read the label back through it
  - Verification: `$ uv run pytest tests/roadmap/stores/test_roadmap_store_contract.py -k one_issue_is_read`
- [x] 2.3 Change each of the 14 direct writes and the intake field loop to `write_status`, with no shim, and list the read-back in the dry-run plans (`StoreRequests.write_status`)
  - Verification: `$ uv run pytest tests/invariants/test_architectural_invariants.py -k status_writer`
- [x] 2.4 Keep the stage, implement, intake, refine, repair, return and claim tests green, and the tests of the dry-run plans
  - Verification: `$ uv run devops ci test tests/roadmap tests/commands/test_pr.py`

## 3. Documents

Kind: documents.

- [x] 3.1 State the one writer in `docs/ROADMAP_WORKFLOW.md` and generate `docs/ERRORS.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The record read-back of the job record goes into `write_status` with #4555.

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
