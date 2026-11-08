# Tasks

## 1. State the budget's subject in the test guide

Reads: `AGENTS.md`, `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [x] 1.1 Add one bullet to the Run time section of `docs/TESTING.md` that states the final rule: the budget measures the mean of the `Tests & Coverage` check, a local `uv run devops ci` runs the whole suite on the logical CPUs of a host that the gates of other agents share, the gate prints the step's time and the slowest tests against `CONST_CI_TEST_BUDGET_SECONDS` (300 s), and no test fails on the time
  - Verification: `$ uv run devops ci docs` passes
- [x] 1.2 Edit `docs/TESTING.md` to state that the budget measures the mean of the `Tests & Coverage` check and that a local full gate can pass it on a shared host
  - Verification: `$ uv run devops ci docs` passes
