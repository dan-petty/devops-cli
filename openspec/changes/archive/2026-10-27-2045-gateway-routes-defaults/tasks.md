# Tasks

## 1. Saved route table keeps only failover state

- [x] 1.1 Write tests in `tests/test_ai_gateway.py` asserting that non-failover routes in a saved state file do not override defaults and that saved failover routes persist on reload, and verify that `uv run devops ci test tests/test_ai_gateway.py` fails on the base
- [x] 1.2 Update `_save_gateway_state` to store only failover routes and `_load_gateway_state` to overlay only failover routes on top of `_build_default_routes()`, and verify that `uv run devops ci test tests/test_ai_gateway.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
