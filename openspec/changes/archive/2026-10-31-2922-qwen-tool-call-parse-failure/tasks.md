# Tasks

## 1. The words of the error

- [x] Write failing tests in `tests/roadmap/test_roadmap_implement_step.py`: the real body of #2747 keeps its quoted words; a token in a quoted word is masked; the echo cases of #2794 still end at `=` or `;`. Change the parameters of the echo test if a quote rule is in them.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`
- [x] Remove `_BODY_QUOTED` from `body_error_text` in `src/devops_cli/roadmap/agent_run.py` and update its docstring and comment.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`

## 2. The line that names the failure

- [x] Write failing tests: a 400 inside a stream that fails on every send gives the line; a 400 outside a stream, a 503 and a context window error give none; the counts of refused commands stay after it.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`
- [x] Add the line in `_model_call_reason` of `src/devops_cli/roadmap/implement_step.py` with `_generation_failed`, and its text to `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`

## 3. The documentation

- [x] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2922-qwen-tool-call-parse-failure`

## Workflow follow-up

- Pending a person: sync the Ollama image pin when ollama/ollama#18571 (or another fix of the `qwen3coder` parser) is in a release.
