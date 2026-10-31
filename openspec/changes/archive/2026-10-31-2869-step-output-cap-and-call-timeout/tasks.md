# Tasks

## 1. The cap and the deadline

- [x] Write failing tests in `tests/roadmap/test_roadmap_implement_step_output_cap.py` and `tests/support/model_script.py`: the first request holds `max_tokens` and `request_timeout` from the constants; a request to the real gateway model holds `max_completion_tokens` and no `request_timeout`; the deadline is less than `router_settings.timeout` of `k8s/llm/gateway/config.yaml`; a call that never answers ends the step with a reason that holds the deadline, and the model gets one request.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_output_cap.py`
- [x] Add the two constants to `src/devops_cli/config/constants.py`. Pass them as `model_settings` in `build_agent`. Add the deadline to `_model_call_reason` and its text to `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_output_cap.py tests/roadmap/test_roadmap_implement_step.py`

## 2. The stop for a capped reply

- [x] Write failing tests in the same file: a text reply with the finish reason `length` stops the step with a reason that holds the cap, with one request and a reset checkout; a tool call with arguments that are not whole and the finish reason `length` stops it the same way; a `write_file` call of three quarters of a small cap passes; the cut call does not run, and the request counts in the outcome; a call that keeps streaming ends at the deadline; the error of a capped reply is a `DevOpsCLIError` with the code `OUTPUT_CAP_REACHED`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_output_cap.py`
- [x] Add `src/devops_cli/roadmap/implement_output_cap.py`, a hook that raises `OutputCapReached` on the finish reason `length`, add it to `build_agent`, and count the cut reply in `_run_turn`. Add the text of the reason to `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_output_cap.py tests/roadmap/test_roadmap_implement_step.py`

## 3. The instructions

- [x] Write a failing test in `tests/roadmap/test_roadmap_implement_step.py`: the instructions tell the model that a reply has an output cap and to write a long file in parts with `edit_file`. Add the bullet to `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`

## 4. The documentation

- [x] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2869-step-output-cap-and-call-timeout`
