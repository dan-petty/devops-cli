# Tasks

## 1. Name the reason of a failed model call

Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, assert that an `AIClientError` names its HTTP status and message in `StageFailure.reason`, hides a quoted part, and logs one line
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage.py`, give the reason and log the line
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
