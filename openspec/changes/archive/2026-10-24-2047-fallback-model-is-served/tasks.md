# Tasks

## 1. The default fallback model is served

- [x] 1.1 Write `test_the_default_fallback_model_is_a_model_that_the_default_ollama_tier_serves` in `tests/test_k8s_llm_gateway.py` with the check of #1969, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py` fails on the base and names the three places with `qwen2.5-coder:7b`
- [x] 1.2 Set `DEFAULT_AI_FALLBACK_MODEL` to `qwen3-coder:30b`, make the harness model slots take the fallback constants, make `tests/test_ai_chaos_model.py` compare the chaos defaults with the constants, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py tests/test_ai_chaos_model.py tests/test_ai_controller.py tests/test_harness_slots.py` passes
- [x] 1.3 Regenerate the option defaults in the documents, and verify that `uv run devops docs generate --sync-readme` and `uv run devops docs check` pass

## 2. Open WebUI names only served models

- [x] 2.1 Write `test_every_open_webui_default_model_is_a_group_that_the_gateway_serves` and its negative control in `tests/test_k8s_llm_gateway.py`, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py` fails on the base on `MODEL_FILTER_LIST`
- [x] 2.2 Remove `MODEL_FILTER_LIST` from `k8s/llm/values-open-webui.yaml`, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py` passes

## Workflow follow-up

- #2125: the default model, the bundle models, the benchmark default and the GPU matrix still name models that the gateway config does not serve.
- Pending a person: after Argo CD syncs the `llm` application, `kubectl -n llm get statefulset open-webui` shows no `MODEL_FILTER_LIST`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
