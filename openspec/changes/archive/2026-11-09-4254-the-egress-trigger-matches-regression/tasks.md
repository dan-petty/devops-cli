# Tasks

## 1. Match a trigger word as a word

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_security.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_security.py`.

- [x] 1.1 Add failing tests: `regression` is no trigger; `egress`, `egress policy`, `egress_policy`, `credentials` and `admission policy` are triggers
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py`
- [x] 1.2 Match each word of `SECURITY_TRIGGER_WORDS` with one compiled pattern in `_matched_security_trigger`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py`

## 2. Check the golden set and the specs

- [x] 2.1 Replay the golden set of the stage eval through the gates
  - Verification: `$ uv run devops roadmap eval stage --replay`
- [x] 2.2 Validate the specs
  - Verification: `$ uv run devops openspec check`
