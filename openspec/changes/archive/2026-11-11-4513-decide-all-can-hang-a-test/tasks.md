# Tasks

## 1. One event loop and a time limit for each request

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/stage/stage_screen_eval.py`. Changes: `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/config/constants.py`, `tests/support/fakes/jev.py`, `tests/roadmap/test_roadmap_decision_step.py`.

- [x] 1.1 Write `test_a_shared_model_serves_every_request_on_one_event_loop` and `test_a_request_that_is_never_answered_ends_in_timeout_error`, and watch them fail on the base (three loops, and the 30 s bound of the test)
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Send all requests of `decide_all` on one event loop with `asyncio.gather`, bound each request with `asyncio.timeout`, and default `timeout` to `CONST_ROADMAP_JEV_TIMEOUT_SECONDS`
  - Verification: `$ uv run pytest -q tests/roadmap/test_roadmap_decision_step.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
