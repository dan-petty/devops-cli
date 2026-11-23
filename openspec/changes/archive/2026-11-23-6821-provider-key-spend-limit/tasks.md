# Tasks

## 1. Behavior: the error of a spent provider key

- [x] 1.1 Write failing tests: a 403 model reply whose body holds OpenRouter's `Key limit exceeded`, as the gateway passes it on, gives `AIKeySpendLimitError` in `model_call_error`, in the gateway chat and stream of `LLMClient`, in the Claude call and in `fetch_model_info`; a 403 with another body gives the credentials error as before; the error text names the spend limit and the person step, and holds no key, URL or amount of the reply
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_spend_limit.py tests/ai/client/test_roadmap_agent_run.py tests/ai/client/test_ai_client_credentials.py`
- [x] 1.2 Add `AIKeySpendLimitError`, `provider_error_text` and `spend_limit_error` to `ai/client/models.py`, the text `ERRORS.ai.provider_key_spend_limit`, and call the rule at each 401/403 site
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_spend_limit.py tests/ai/client/test_roadmap_agent_run.py tests/ai/client/test_ai_client_credentials.py tests/ai/client/test_ai_client_error_reason.py tests/ai/mcp/test_ai_gateway.py`

## 2. Behavior: the failure class `spend_limit`

- [x] 2.1 Write failing tests: the taxonomy has 24 classes with `spend_limit`, its default action is `wait`, `failure_class_of` gives it for `AIKeySpendLimitError`, `RETRY_AFTER` gives it 1 hour, the error line of a stage Job log gives it before an earlier timeout line, the stage Job exits 1 with the error line, and the implement row counts an ended Job whose log holds the error under `spend_limit`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/stage/test_roadmap_stage_job_entry.py tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 2.2 Add the class, its action, its entry in `CLASS_BY_EXCEPTION` and `RETRY_AFTER`, and the text rule made from the message
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/stage/test_roadmap_stage_retry_after.py tests/roadmap/stage/test_roadmap_stage_job_entry.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_faults.py`

## 3. Manifests: the alert

- [x] 3.1 Add `RoadmapProviderKeySpendLimit` to the group `roadmap-service` and its promtool unit tests
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 4. Documents

- [x] 4.1 Name the class in docs/ROADMAP_WORKFLOW.md and docs/roadmap/stage.md, and the alert and the person step in docs/CLUSTER.md and k8s/README.md, and regenerate the documentation with `devops docs generate` for the new error class and message
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
