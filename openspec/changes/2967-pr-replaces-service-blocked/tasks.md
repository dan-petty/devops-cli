# Tasks

## 1. Replace a Blocked Status that a stop recorded

Kind: behavior

Reads: `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/status_sync.py`, `tests/commands/test_pr_status.py`. Changes: `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stop_clear.py`, `tests/commands/test_pr_status.py`.

- [x] 1.1 In `tests/commands/test_pr_status.py`, write cases for an item that a stop of a job set Blocked (its Status and `implement.stopped` recorded with `store.set_field`): `set_delivered_status` sets In Progress and sets In Review. Change the existing Blocked cases so the item is Blocked by a person, and add a case for a recorded Blocked with no stop on record
  - Verification: `uv run devops ci test tests/commands/test_pr_status.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/status_sync.py`, add `holds_service_stop(item)`. In `src/devops_cli/roadmap/stop_clear.py`, make `is_service_stop` call it. In `src/devops_cli/roadmap/pull_status.py`, let `set_delivered_status` replace the Status of an item for which `holds_service_stop` is true, and update the module docstring
  - Verification: `uv run devops ci test tests/commands/test_pr_status.py tests/roadmap/test_roadmap_stop_clear.py` passes

## 2. Describe the rule in the workflow document

Kind: documents

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 2.1 In `docs/ROADMAP_WORKFLOW.md`, add the rows of the state table for `devops pr create` and `devops pr ready` on a `status/blocked` Item with `implement.stopped`
  - Verification: `uv run devops ci docs`

## Criteria

- Group 1: `set_delivered_status` SHALL set the target Status on an item that is Blocked, whose recorded Status is Blocked and whose record holds `implement.stopped`.
- Group 1: `set_delivered_status` SHALL leave an item that is Blocked with no such record.
- Group 1: `is_service_stop` SHALL keep its state, claim and Job checks.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
