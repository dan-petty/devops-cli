# Tasks

## 1. Behavior

- [x] 1.1 Add tests to `tests/ci/test_ci_gate_slots.py`: a held slot marks the environment of its holder and of the children that it starts, a direct run waits while a gate holds the only slot, a run that a gate started takes no slot and keeps its workers, and a direct run starts at most the CPUs of one slot
  - Verification: `$ uv run devops ci test tests/ci/test_ci_gate_slots.py`
- [x] 1.2 Set `DEVOPS_CLI_GATE_SLOT_HELD` in `gate_slot`, add `direct_run_slot` to `src/devops_cli/ci/gate_slots.py`, and call it from a `pytest_xdist_auto_num_workers` wrapper in `tests/conftest.py`
  - Verification: `$ uv run devops ci test tests/ci/test_ci_gate_slots.py tests/ci/test_ci_gate_admission.py`

## 2. Documents

- [x] 2.1 Say in `CONTRIBUTING.md` and `docs/TESTING.md` which pytest runs take a gate slot
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
