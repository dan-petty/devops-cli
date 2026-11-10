# Tasks

## 1. Judge the code that a scenario tests

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`, assert that a data file in the `when` that no group touches needs no test text, and that a `then` path, a `when` path that a group changes or reads, and a `then` identifier with no test are refused
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, choose the judged spans of a scenario in `_judged_spans`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
