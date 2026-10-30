# Tasks

## 1. The failing tests

- [x] Write failing tests in `tests/test_roadmap_implement_step.py` and `tests/test_roadmap_implement_job.py`: a model call that fails in the first turn and in the extra turn for the ticks, with `ModelAPIError`, `ModelHTTPError` (503) and `ModelRequestTimeout`, gives a stopped outcome with the reason, the masked diff, the requests, the tokens and the last text, and resets the checkout; the message and the body of the error, with a secret in a dict body, stay out of the reason; a failed read of the diff keeps the reason of the stop; the ledger holds the spend of the failed turn; a refused key (401, 403) in either turn still raises `AICredentialsError` after the reset; a job stop comment holds the diff; a refused key stops the whole job.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 2. The stop for a failed model call

- [x] Change `_run_agent` in `src/devops_cli/roadmap/implement_step.py`: a `ModelAPIError` that is not a refused key ends the turn as stopped with `_stop_reason` and the last text, and a refused key raises `AICredentialsError` after the `finally` block. Fix the docstrings of `_run_agent` and `run_step`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 3. The documentation

- [ ] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2731-keep-diff-on-model-failure`
