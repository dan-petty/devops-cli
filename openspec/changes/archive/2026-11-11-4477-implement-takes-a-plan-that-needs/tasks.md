# Tasks

## 1. Leave out a Staged item whose draft holds the label plan/needs-fix

Reads: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/github/client.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`. Changes: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`.

- [x] 1.1 Add to `tests/roadmap/implement/test_roadmap_implement_selection.py` a test that a Staged item whose open draft holds `plan/needs-fix` gets no target and a reason that names the label and the pull request. Add to `tests/roadmap/implement/test_roadmap_implement_submit.py` a test that two rounds create no Job, log the item once and record `implement.needs_fix`, a test that a round after the label is gone creates the Job and clears the mark, and a test that a label that comes back is logged again. Add `implement.needs_fix` to the table of `tests/roadmap/implement/test_roadmap_implement_record_readers.py`
  - Verification: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/implement/test_roadmap_implement_record_readers.py` fails on the base
- [x] 1.2 Leave out an open draft with `PLAN_NEEDS_FIX_LABEL` in `_Judge._pull_reason`, keep the item in `ImplementPlan.needs_fix`, add `ImplementRecordKey.NEEDS_FIX`, record and clear the mark in `run_implement_round`, and log each new item in the row `implement` of `run.py`
  - Verification: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/implement/test_roadmap_implement_record_readers.py` passes

## 2. Name the reason and the mark in the documents

Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Add the label to the reasons that the implement job leaves an item out in `docs/roadmap/implement.md`, and add `implement.needs_fix` to the record table of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
