# Tasks

## 1. Behavior

- [x] 1.1 Update `check_gates` and `check_proposal` to require keyword-only `registry` parameter
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_gates.py`
- [x] 1.2 Update `replay_all` and `replay_case` to require keyword-only `registry` parameter
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
- [x] 1.3 Add ast-grep rule `stage-registry-cwd-read` and register in construct gates
  - Verification: `$ uv run devops ci --check --only constructs`
- [x] 1.4 Cache `registry_table` once per run in `_Planner` and `_Judge`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_plan.py`

## 2. Documents

- [x] 2.1 Set `skip_specs: true` in `.openspec.yaml` and document change in OpenSpec change folder
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
