# Tasks

## 1. The review plans take the model endpoint from the configuration

Kind: behavior. Reads: `src/devops_cli/ai/endpoints.py`, `src/devops_cli/ai/review/runner.py`. Changes: `tests/review/test_review_plan_model_endpoint.py`, `tests/commands/test_review_dry_run.py`, `src/devops_cli/review/review_plans.py`.

- [x] 1.1 Write the failing tests: a gateway with no `ai.gateway_url` plans `<ai.gateway_url>/chat/completions`, a configured gateway URL gets no second `/v1`, Ollama with no URLs plans `<ai.ollama_urls>/api/chat` and `<ai.ollama_urls>/api/embeddings`, Claude plans `/v1/messages`, and the `analysis` task provider wins; `devops review path src --dry-run` with no `ai.gateway_url` prints the placeholder and exits 0
  - Verification: `$ uv run devops ci test tests/review/test_review_plan_model_endpoint.py tests/commands/test_review_dry_run.py`
- [x] 1.2 Resolve the plan targets with `resolve_ai_endpoint`, show the setting of a `ConfigurationError` as the placeholder, and delete the fixed gateway host and the two localhost fallbacks
  - Verification: `$ uv run devops ci test tests/review/test_review_plan_model_endpoint.py tests/commands/test_review_dry_run.py`

## Workflow follow-up

- The nine localhost fallbacks of `src/devops_cli/ai/ai_plans.py`, its gateway and Qdrant fallbacks, and a guard rule that matches a fallback list: #5395.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
