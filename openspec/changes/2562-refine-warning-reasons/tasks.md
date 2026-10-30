# Tasks

## 1. The error carries its status and timeout

- [ ] 1.1 Write failing tests in `tests/test_ai_client_error_reason.py`: the `reason` of an error with a status, a timeout and neither; an OpenAI-style HTTP 408 reply with the body `MODEL-TEXT` gives status 408 and a `reason` with no `MODEL-TEXT`; an error frame with a status in its body gives that status; a read timeout gives `timed_out`; and in `tests/test_roadmap_agent_run.py` `model_call_error` for `ModelHTTPError(504)` and `ModelTimeoutError`.
  - Verification: `uv run devops ci test tests/test_ai_client_error_reason.py tests/test_roadmap_agent_run.py`
- [ ] 1.2 Add `status`, `timed_out` and `reason` to `AIClientError` in `src/devops_cli/ai/client/models.py`. Set them in `_status_error` (`openai.py`), `_map_openai_error` for a timeout, `_format_status_error` and `_format_network_error` (`base.py`), the status branch of `claude.py`, and `model_call_error` (`roadmap/agent_run.py`).
  - Verification: `uv run devops ci test tests/test_ai_client_error_reason.py tests/test_roadmap_agent_run.py tests/test_ai_client_retries.py`

## 2. The two warnings

- [ ] 2.1 Write failing tests in `tests/test_roadmap_refine.py` and `tests/test_roadmap_refine_investigation.py`: the warning of a failed call names the repository, the code and the status or `timeout`; the warning of a stopped investigation names the repository, the class and the first line of the message; the body, the second line of the message and a token never appear in the log, the error of the round, the record or the comment.
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py`
- [ ] 2.2 Add `run_error_message` to `src/devops_cli/roadmap/agent_run.py` and the limits to `src/devops_cli/config/constants.py`. Give `InvestigationStopped` the field `message`. Pass `repo` from `plan_refine` to `refine_one_item`, `_investigate` and `_failed_item`, and write the two warnings.
  - Verification: `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_refine_investigation.py tests/test_roadmap_alternatives.py`

## 3. The documentation

- [ ] 3.1 Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] 4.1 Archive the change.
  - Verification: `uv run devops openspec archive 2562-refine-warning-reasons`

## Workflow follow-up

- The implement step builds its stop reason from `str(stopped)`, which holds the `body` of an `UnexpectedModelBehavior`. The follow-up issue is filed with `devops roadmap intake`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
