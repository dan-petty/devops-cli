# Tasks

## 1. The Service limits its model calls to a configured count in flight

- [x] 1.1 Write `test_dispatch_calls_hold_the_model_call_slot` and `test_the_model_call_slot_admits_only_its_limit` in `tests/test_ai_client_network.py`, and `test_the_service_keeps_one_model_call_in_flight_by_default` and `test_the_service_installs_its_model_call_limit` in `tests/test_service_limits.py`, and verify that `uv run devops ci test tests/test_ai_client_network.py tests/test_service_limits.py` fails on the base: a dispatch call sends with no per-Service limit
- [x] 1.2 Add the model call slot and its setter in `src/devops_cli/ai/client/network.py`, hold the slot around the model call in `_dispatch_messages` in `src/devops_cli/ai/client/unified.py`, add `service.model_call_concurrency` and its default in `src/devops_cli/config/settings.py` and `src/devops_cli/config/defaults.py`, set the slot at start in `src/devops_cli/server/service.py`, and reset the slot after each test in `tests/conftest.py`, and verify that `uv run devops ci test tests/test_ai_client_network.py tests/test_service_limits.py tests/test_architectural_invariants.py` passes
- [x] 1.3 Regenerate the configuration documents, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff.
