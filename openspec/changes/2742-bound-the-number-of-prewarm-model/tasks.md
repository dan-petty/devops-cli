# Tasks

## 1. Bound the model label and the span attribute of a prewarm run

Kind: behavior. Reads: `src/devops_cli/commands/ai.py`, `src/devops_cli/ai/endpoints.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/ai/client/unified.py`, `tests/support/fakes/otlp.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/commands/ai.py`, `tests/support/fakes/model.py`, `tests/ai/mcp/test_ai_prewarm.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`.

- [ ] 1.1 Write failing tests, and change the 11 test cases that hold the old label and traffic. In `tests/support/fakes/model.py`, give `ModelFake.list_models` the argument `urls` and a list `list_models_calls`. In `tests/ai/mcp/test_ai_prewarm.py`, drive `devops ai prewarm` through `cli`, `model_fake` and `otlp`, and read the counter points and the `ai.prewarm` spans for the scenarios of the two requirements: a model that no server reports gives `other` in both records, `ai.model` and a reported model pass, a reported model with symbols or of 300 characters gets the inner bound, a failing `list_models` (`AIClientError`) gives `other` and the prewarm still runs, `--url` asks only the named server, and `ai.provider` `openai` asks no server. In `tests/ai/client/test_ai_client_providers_and_embeddings.py`, add a test that `list_models(urls=[...])` of the Ollama client sends its request to the named URL only. Give the 5 cases of the label test and the 2 cases of the counter test `model_fake.set_available_models`. Make the 3 traffic tests of `TestPrewarmToolTakesNoUrlFromTheModel` (4 failing cases) count the `POST /api/generate` requests and dials of the prewarm (script one more answer for each `GET /api/tags`)
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_ai_prewarm.py tests/ai/client/test_ai_client_providers_and_embeddings.py` fails on the base
- [ ] 1.2 Add `CONST_METRIC_LABEL_OTHER` and `bounded_model_label` and change the description of `AI_PREWARMS_TOTAL`. Give `list_models` and `_ollama_models` the optional `urls`. In `prewarm`, for the provider `ollama`, call `client.list_models(urls=[server])` for each server of the run, catch `AIClientError` and `ConfigurationError`, set the span attribute `ai.model` and give the counter the same label
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_ai_prewarm.py tests/ai/client/test_ai_client_providers_and_embeddings.py tests/commands/test_ai_cmd.py`

## 2. Documents

Kind: other. Reads: `src/devops_cli/telemetry/instruments.py`. Changes: `docs/TELEMETRY.md`.

- [ ] 2.1 Run `uv run devops docs generate --sync-readme`. Only `docs/TELEMETRY.md` changes
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
