# Tasks

## 1. Runner in-pod reply text capture

- [x] 1.1 Add failing unit tests asserting `run_level` collects and returns response text when `return_replies` is enabled (`uv run devops ci test tests/test_ai_gateway_tune.py`).
- [x] 1.2 Extend `run_level` in `src/devops_cli/ai/gateway_bench.py` to capture and return reply content from choices (`uv run devops ci test tests/test_ai_gateway_tune.py`).
- [x] 1.3 Regenerate command documentation (`uv run devops docs generate --sync-readme`).

## 2. Capability probe definitions and scoring

- [x] 2.1 Add failing unit tests asserting four capability probes evaluate with `pydantic_evals` and record `was_repaired` from response repair (`uv run devops ci test tests/test_ai_gateway_tune.py`).
- [x] 2.2 Implement four capability probes, deterministic evaluators, and repeated trial evaluation in `src/devops_cli/ai/gateway_tune.py` (`uv run devops ci test tests/test_ai_gateway_tune.py`).
- [x] 2.3 Regenerate command documentation (`uv run devops docs generate --sync-readme`).

## 3. Gateway tune reporting and persistence

- [x] 3.1 Add failing tests for gateway tune command output and run store persistence of probe results (`uv run devops ci test tests/test_ai_gateway_tune.py`).
- [x] 3.2 Update `tune_pool` and `_render_tune_report` in `src/devops_cli/commands/ai_gateway.py` to execute probes, report pass rates or unmeasured status, and persist records (`uv run devops ci test tests/test_ai_gateway_tune.py`).
- [x] 3.3 Regenerate command documentation (`uv run devops docs generate --sync-readme`).

## Workflow follow-up

- Slice 2: Replace parameter-count floors in routing with probe records (#478 follow-up).
- Slice 3: Client-side floor check on served_by (#474).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
