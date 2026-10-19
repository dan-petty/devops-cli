# Task: One Model Seam (#1001)

**Issue**: [#1001](https://github.com/dan-petty/devops-cli/issues/1001)
**Scope**: scope/ai
**Feasibility**: Verified against ADR 0007 ("Tests double only process edges, through seams"), pydantic-ai `Model` abstract base class, and `pydantic_ai.direct` (`model_request_sync`, `model_request_stream_sync`). Verified that `ModelFake` implements both `pydantic_ai.models.Model` and `LLMClient` duck typing offline without network, passes the 16-test contract suite in `tests/test_model_contract.py` with each call phase $\le 1.0$ s, and re-exports cleanly via `tests.support.fakes`.

## Description

Tests double only process edges through seams (ADR 0007). The model edge is one of the four foundational process edges requiring a shared in-memory fake and a comprehensive contract suite. This item delivers the model seam across several pull requests.

**Part 1: In-memory `ModelFake` and contract suite (PR #1700, merged).**

- **The fake (`tests/support/fakes/model.py`).** `ModelFake` implements `pydantic_ai.models.Model` (providing `request()`, `request_stream()`, and model identification) and ducks `LLMClient` methods (`chat()`, `chat_messages()`, `chat_stream()`, `list_models()`, `embed()`). It supports queued responses (`fake.answer(...)`), pattern and predicate routing (`fake.route(...)`), error injection (`fake.route_error(...)`), deterministic unit-normalized embeddings (`fake.embed(...)` / `deterministic_embedding`), and invocation inspection (`fake.sent`, `fake.requested`, `fake.call_count`, `fake.reset()`). Marked with `__test__ = False` to prevent pytest collection warnings.
- **Re-exports (`tests/support/fakes/__init__.py`).** Exposes `ModelFake`, `ModelCall`, `ModelAnswer`, and `deterministic_embedding` in the shared fake namespace.
- **Contract suite (`tests/test_model_contract.py`).** Tests the promises of the model edge: completion, streaming, thinking extraction, finish reason mapping, token usage, error propagation, sequential answering, pattern routing, deterministic unit-normalized embeddings, and model listing. Validates both `ModelFake` and real implementations (`pydantic_ai.models.test.TestModel`, `LLMClient` over recorded frames) offline without network.
- **Conftest fixture held.** Edits to `tests/conftest.py` and the shared `model_fake` pytest fixture are held until #1312 PR 3 merges (which registers `tests/support/` modules as plugins and refactors the root conftest).

**Part 2: Provider adapters with egress factory, direct spend tracking, and private import retirements (this PR).**

- **Egress factory injection (`src/devops_cli/ai/providers/__init__.py`).** `create_pydantic_ai_provider` injects `http_client=new_async_http_client(level=level)` on providers whose constructor accepts `http_client` (`OpenAIProvider`, `AnthropicProvider`, `OllamaProvider`, etc.), enforcing bounded timeouts, connection pooling, and SSRF guardrails through the egress factory.
- **Direct spend tracking rebuild (`src/devops_cli/ai/direct.py`).** Direct completion (`direct_model_request_sync`, `direct_model_request`) and streaming (`direct_model_request_stream_sync`, `direct_model_request_stream`) track model spend into the ledger with accurate metadata (extracting provider from model system, server from base URL, served-by from gateway tags, finish reason, and token usage). Stream spend records upon generator completion inside `try...finally`.
- **Gateway tagging (`src/devops_cli/ai/pydantic_ai_bridge.py`).** Gateway-resolved remote models are tagged with `served_by=base_url` for multi-backend attribution.
- **Retire private pydantic-ai imports.** Replaced `pydantic_ai._run_context` with public `from pydantic_ai import RunContext as NativeRunContext` in `src/devops_cli/ai/agents/agent.py` and `context.py`. Retired redundant `resolve_model_id_sync` reaching `_models_by_id` in `src/devops_cli/ai/durable.py` in favor of public async `resolve_model_id`.
- **Constants update (`src/devops_cli/config/constants.py`).** Removed `"direct"` from `CONST_LOCAL_TRANSPORT_LABELS` so direct requests record true provider and server attribution rather than classifying as local/none.

**Subsequent parts of #1001.**

- Conftest fixture registration and test suite migration: PR 3 of #1001 (once #1312 PR 3 merges).
- Factory consolidation (`src/devops_cli/ai/client/factory.py`), removing inline `LLMClient(...)` instantiations, deleting `config/settings.py:get_llm_client`: PR 4 of #1001.
- Final caller cleanups, changelog fragment `changelog.d/1001.md`, and issue close: PR 5 of #1001.

## Acceptance Criteria

- [x] Ships `ModelFake` under `tests/support/fakes/model.py` and re-exports in `tests/support/fakes/__init__.py` with `__test__ = False`.
- [x] Implements both `pydantic_ai.models.Model` interface and `LLMClient` duck typing (sync completion, streaming, model listing, deterministic embeddings).
- [x] Contract suite in `tests/test_model_contract.py` validates fake and real implementations (`TestModel`, `LLMClient` over recorded mock frames) offline without network.
- [x] Each test call phase stays under 1.0 s, and all 16 contract tests pass.
- [x] `create_pydantic_ai_provider` injects `http_client` from the egress factory into pydantic-ai providers accepting it.
- [x] Direct spend tracking in `src/devops_cli/ai/direct.py` attributes provider, server, served-by, tokens, and finish reason across sync, async, and streaming direct requests.
- [x] Retired private `pydantic_ai._run_context` and `_models_by_id` references in `src/devops_cli/ai/`.
- Conftest fixture `model_fake`: held until #1312 PR 3 merges.
- Client factory consolidation and removal of inline `LLMClient(...)` calls: subsequent PR of #1001.
- Changelog fragment `changelog.d/1001.md`: final PR of #1001 that closes the issue.
- Pending a person: `devops ai chat`, one `devops review path`, and `devops rag query` run against the gateway and against a local Ollama.

## Deliverables

- [x] `tests/support/fakes/model.py`: In-memory `ModelFake`, `ModelCall`, `ModelAnswer`, and `deterministic_embedding`.
- [x] `tests/support/fakes/__init__.py`: Re-export model fake symbols.
- [x] `tests/test_model_contract.py`: 16 contract tests covering fake and real implementations.
- [x] `src/devops_cli/ai/providers/__init__.py`: Inject egress factory HTTP client into providers.
- [x] `src/devops_cli/ai/direct.py`: Rebuilt direct spend tracking with provider/server attribution and streaming spend recording.
- [x] `src/devops_cli/ai/pydantic_ai_bridge.py`: Gateway `served_by` tagging.
- [x] `src/devops_cli/ai/agents/agent.py`: Public `RunContext` import.
- [x] `src/devops_cli/ai/agents/context.py`: Public `RunContext` import.
- [x] `src/devops_cli/ai/durable.py`: Retired private `_models_by_id` sync method.
- [x] `src/devops_cli/config/constants.py`: Removed `"direct"` from `CONST_LOCAL_TRANSPORT_LABELS`.
- [x] `docs/agent/tasks/task-1001-one-model-seam.md`: Task tracking file for Part 1 & Part 2 of #1001.
- PR 3 to PR 5: see Description.
