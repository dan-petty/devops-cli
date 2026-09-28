# Task 455: Provider Gateway Talks Only to the Gateway

**Issue**: [#455](https://github.com/dan-petty/devops-cli/issues/455)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/security`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

`OpenAICompatProviderMixin._api_base` returned `api_base_url` before it considered `gateway_url`,
and `AIConfig.for_task` copied the global `api_base_url` into every task. A global
`api_base_url` is usually set for the `openai` provider. A task with `provider: gateway`
therefore sent its requests, with `Authorization: Bearer <gateway key>`, to OpenAI. The gateway
master key had to be rotated after it was sent to a third party.

The same inheritance let a task that switched to any other provider (for example `claude`) send
its key to the global provider's endpoint. The pydantic-ai bridge resolved `litellm:` models to
`api_base_url` without checking `gateway_url`, and hard-coded the `portkey:` and `lightllm:`
endpoints instead of using `portkey_url` and `lightllm_url`.

### Key Deliverables Completed:

- [x] **One Gateway Address**: provider `gateway` always sends to `gateway_url`. `_api_base`,
  `LLMClient.backend_host` and gateway embeddings no longer consult `api_base_url` for it.
- [x] **Task Endpoint Resolution** (`AIConfig._task_endpoint_updates`): a task's own
  `api_base_url` applies to its provider. On a gateway task it becomes that task's
  `gateway_url`. The global `api_base_url` carries over only to tasks that keep the global
  provider.
- [x] **Bridge Gateway Prefixes**: `litellm:`, `portkey:` and `lightllm:` resolve to
  `gateway_url`, `portkey_url` and `lightllm_url`.
- [x] **Embeddings**: `EmbeddingsEngine` drops its private copy of the embedding task's
  `api_base_url` and uses the shared resolution.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_gateway_base_url.py`: gateway task vs global `api_base_url`, task-level
    override, global gateway provider, provider-switching tasks, bridge prefixes.
  - `tests/test_rag_embeddings.py`: an embedding task on the gateway under a global OpenAI setup.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The test used a configuration with global provider `ollama`, global `api_base_url` set to OpenAI
and chat on `provider: gateway`, without the per-task `api_base_url` workaround. Both gateway
tasks resolved to the gateway, and a chat request went to it and got an answer.
