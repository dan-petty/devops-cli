# Tasks

## 1. The gate test holds the self-acceptance test (other)

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_gates.py`, set the `test` field of the changed group of `test_a_stage_check_change_with_no_replay_task_is_a_problem_of_the_gate_eval_replay` to a sentence that holds `StageProposal`, `content_problems` and `no problem`.
  Verification: `uv run pytest tests/roadmap/test_roadmap_stage_gates.py`
- [x] 1.2 Check that the change folder is valid
  Verification: `uv run devops openspec check`
