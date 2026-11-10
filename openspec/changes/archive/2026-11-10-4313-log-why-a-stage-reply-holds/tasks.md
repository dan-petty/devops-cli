# Tasks

## 1. Log the stop facts of a refused reply

Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, `tests/support/scripted_model.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, assert that the line of a degenerate reply holds `tool_calls`, `limit`, `finish_reason` and `answered`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/agent_run.py` and `src/devops_cli/roadmap/stage/stage.py`, keep the stop reason and the model name of the last reply and print the four fields
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: read the new line after the next deploy, and fix the cause at its source in a later change.
