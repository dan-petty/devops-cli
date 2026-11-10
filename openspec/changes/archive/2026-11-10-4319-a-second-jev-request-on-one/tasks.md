# Tasks

## 1. Behavior

- [x] 1.1 Write the failing test: two requests on one model to a keep-alive server on loopback
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `decide_with_jev` on one persistent loop, remove `_run_decide`, and move the helpers, `jev_ask.py` and `jev_completeness.py` to it
  - Verification: `$ uv run devops ci test tests/ai/test_jev_one_model_many_requests.py tests/ai/test_jev_gateway_route.py tests/roadmap/test_jev_completeness_eval.py`

## 2. Documents

- [x] 2.1 Check that no document names the removed `_run_decide`
  - Verification: `$ ! git grep -n -F _run_decide -- src tests docs README.md`
