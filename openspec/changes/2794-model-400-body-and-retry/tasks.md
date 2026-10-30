# Tasks

## 1. The body in the reason

- [x] Write failing tests in `tests/test_roadmap_implement_step.py`: the reason of a `ModelHTTPError` with the status 400 holds the `message` of a dict body, the string of a `{"error": "..."}` body, and a string body; a token in the text is masked; a long text is cut; a body of other values (`api_key`, headers) adds nothing; a `ModelAPIError` adds nothing. Change the tests of #2731 that say the body stays out.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Add the text of the body to the reason in `_model_call_reason` of `src/devops_cli/roadmap/implement_step.py`, and the format to `src/devops_cli/lang/en/messages.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`

## 2. The resend

- [ ] Write failing tests in `tests/test_roadmap_implement_step.py`, with a way in `tests/support/model_script.py` to fail inside a stream: one failure then a good reply ends done with the same messages in both requests; every send fails and the step stops with the body and the count of requests; a 400 before a stream, a 503 and a context window error get no second request; one failure in the extra turn; the requests of both sends count in the limit of requests.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [ ] Add `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` to `src/devops_cli/config/constants.py`. Split `_run_agent` into a turn and a loop that resumes the conversation after an error of the generation inside a stream.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 3. The documentation

- [ ] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2794-model-400-body-and-retry`
