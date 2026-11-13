# Tasks

## 1. A skip by a when that names check mode is unchecked

Kind: behavior. Changes: `src/devops_cli/infra/plan.py`, `tests/infra/test_plan.py`, `tests/support/infra.py`, `tests/fixtures/infra/runner_events/probe/`, `tests/fixtures/infra/runner_events/check_when.jsonl`.

- [x] 1.1 Add the play `check_when.yaml` and the host node-5 to the probe, record the run `check_when` with the pinned `ansible-runner`, and add `tests/infra/test_plan.py::test_a_skip_by_a_when_that_names_check_mode_is_unchecked`. It fails: the plan of node-5 has no unchecked task.
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` fails on the base
- [x] 1.2 In `plan.py`, show a skip by a false `when` item that names `ansible_check_mode` as unchecked, for a task and for a loop item.
  - Verification: `$ uv run devops ci test tests/infra/`

## 2. Documents

Kind: other. Changes: `src/devops_cli/infra/plan.py` (module docstring), `tests/support/infra.py` (docstring).

- [x] 2.1 Give the rule in the module docstring of `plan.py`, and the recording of `check_when` in the docstring of `tests/support/infra.py`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The gVisor play of the infra repository uses such a `when` for the install of `runsc` and the reads of the CRI config. Its first plan after this change shows them as unchecked.
