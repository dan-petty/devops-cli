# Task: One Model Seam (#1001)

**Issue**: [#1001](https://github.com/dan-petty/devops-cli/issues/1001)
**Scope**: scope/ai
**Feasibility**: Verified against ADR 0007 ("Tests double only process edges, through seams"), pydantic-ai `Model` abstract base class, and `pydantic_ai.direct` (`model_request_sync`, `model_request_stream_sync`). Verified that `ModelFake` implements both `pydantic_ai.models.Model` and `LLMClient` duck typing offline without network, passes the 16-test contract suite in `tests/test_model_contract.py` and 8 fixture tests in `tests/test_model_fixture.py` with each call phase $\le 1.0$ s, and re-exports cleanly via `tests.support.fakes`.

## Description

Tests double only process edges through seams (ADR 0007). The model edge is one of the four foundational process edges requiring a shared in-memory fake and a comprehensive contract suite. This item delivers the model seam across five pull requests.

**Part 1: In-memory `ModelFake` and contract suite (PR #1700, merged).**

- **The fake (`tests/support/fakes/model.py`).** `ModelFake` implements `pydantic_ai.models.Model` (providing `request()`, `request_stream()`, and model identification) and ducks `LLMClient` methods (`chat()`, `chat_messages()`, `chat_stream()`, `list_models()`, `embed()`). It supports queued responses (`fake.answer(...)`), pattern and predicate routing (`fake.route(...)`), error injection (`fake.route_error(...)`), deterministic unit-normalized embeddings (`fake.embed(...)` / `deterministic_embedding`), and invocation inspection (`fake.sent`, `fake.requested`, `fake.call_count`, `fake.reset()`). Marked with `__test__ = False` to prevent pytest collection warnings.
- **Re-exports (`tests/support/fakes/__init__.py`).** Exposes `ModelFake`, `ModelCall`, `ModelAnswer`, and `deterministic_embedding` in the shared fake namespace.
- **Contract suite (`tests/test_model_contract.py`).** Tests the promises of the model edge: completion, streaming, thinking extraction, finish reason mapping, token usage, error propagation, sequential answering, pattern routing, deterministic unit-normalized embeddings, and model listing. Validates both `ModelFake` and real implementations (`pydantic_ai.models.test.TestModel`, `LLMClient` over recorded frames) offline without network.
- **Conftest fixture held.** Edits to `tests/conftest.py` and the shared `model_fake` pytest fixture were held until #1312 PR 3 merged.

**Part 2: Provider adapters with egress factory, direct spend tracking, and private import retirements (PR #1702, merged).**

- **Egress factory injection (`src/devops_cli/ai/providers/__init__.py`).** `create_pydantic_ai_provider` injects `http_client=new_async_http_client(level=level)` on providers whose constructor accepts `http_client` (`OpenAIProvider`, `AnthropicProvider`, `OllamaProvider`, etc.), enforcing bounded timeouts, connection pooling, and SSRF guardrails through the egress factory.
- **Direct spend tracking rebuild (`src/devops_cli/ai/direct.py`).** Direct completion (`direct_model_request_sync`, `direct_model_request`) and streaming (`direct_model_request_stream_sync`, `direct_model_request_stream`) track model spend into the ledger with accurate metadata (extracting provider from model system, server from base URL, served-by from gateway tags, finish reason, and token usage). Stream spend records upon generator completion inside `try...finally`.
- **Gateway tagging (`src/devops_cli/ai/pydantic_ai_bridge.py`).** Gateway-resolved remote models are tagged with `served_by=base_url` for multi-backend attribution.
- **Retire private pydantic-ai imports.** Replaced `pydantic_ai._run_context` with public `from pydantic_ai import RunContext as NativeRunContext` in `src/devops_cli/ai/agents/agent.py` and `context.py`. Retired redundant `resolve_model_id_sync` reaching `_models_by_id` in `src/devops_cli/ai/durable.py` in favor of public async `resolve_model_id`.
- **Constants update (`src/devops_cli/config/constants.py`).** Removed `"direct"` from `CONST_LOCAL_TRANSPORT_LABELS` so direct requests record true provider and server attribution rather than classifying as local/none.

**Part 3: Client factory consolidation and deleting `config/settings.py:get_llm_client` (PR #1704, merged).**

- **The factory (`src/devops_cli/ai/client/factory.py`).** Implements `get_llm_client(task, config, settings, model, api_key, cache_enabled, **kwargs)` and alias `build_llm_client`. Builds clients per task with active settings, task-specific configurations, API keys from settings/keyring/env, model overrides, and cache controls.
- **Deleting `config/settings.py:get_llm_client`.** Removed `get_llm_client` from `config/settings.py`, eliminating the circular coupling from `config` into `ai/client`. Re-exported `get_llm_client` and `build_llm_client` directly in `devops_cli.ai.client`.
- **Routing inline constructions.** Replaced all 26 inline `LLMClient(...)` instantiations across `src/devops_cli/` with `get_llm_client(...)`.
- **Unit tests (`tests/test_ai_client_factory.py`).** Comprehensive unit tests verifying factory defaults, task routing, explicit configurations, model overrides, key propagation, and the absence of `get_llm_client` on `config.settings`.

**Part 4: Conftest fixture registration, factory seam, and initial test suite migrations (PR #1705, merged).**

- **The fixture (`tests/conftest.py:model_fake`).** Following the merge of #1312 PR 3, registered the `model_fake` fixture in root `conftest.py`. Installs an in-memory `ModelFake` instance into the client factory seam using `monkeypatch.setattr(factory, "_client_override", fake)`.
- **Factory seam (`src/devops_cli/ai/client/factory.py`).** Introduced `_client_override` and `set_llm_client_override` in the client factory. When active, `get_llm_client` and `build_llm_client` immediately return the installed fake without opening sockets or initializing external providers.
- **ModelFake enhancements (`tests/support/fakes/model.py`).** Equipped `ModelFake` with `chat_messages_stream`, `chat_structured`, and `preload_models` ducking to support structured output validation and multi-message streaming.
- **Fixture test suite (`tests/test_model_fixture.py`).** 8 tests validating factory injection, sequential answering, pattern and error routing, synchronous token streaming, deterministic embeddings, model listing, structured completion, and direct pydantic-ai requests.
- **Test suite migrations.** Migrated `tests/test_instruction_generator.py` and `tests/test_roadmap_refine.py` to use `model_fake` instead of internal module patches on `LLMClient` or `get_llm_client`.

**Part 5: Final caller test migrations, egress ssrf cleanup, changelog fragment, and issue close (this PR).**

- **Caller test migrations.** Migrated remaining test suites in `tests/test_ai_prewarm.py`, `tests/test_ai_chaos_model.py`, and `tests/test_ai_cmd.py` away from internal `LLMClient` monkeypatches to the shared `model_fake` fixture.
- **Client ducking completion (`tests/support/fakes/model.py`).** Added `backend_info`, `_FakeConfig`, `factory_calls`, `preload_calls`, `set_preload_results`, `set_available_models`, `set_list_models_error`, and sequential answer repeating semantics to `ModelFake`.
- **Factory call tracking (`src/devops_cli/ai/client/factory.py`).** Added dispatch to `_client_override.record_factory_call` when present to record factory parameters during test assertions.
- **SSRF cleanup (`src/devops_cli/http/egress.py`).** Replaced direct import from `pydantic_ai._ssrf` with `from devops_cli.core.validation import is_cloud_metadata_ip`.
- **Changelog fragment (`changelog.d/1001.md`).** Documented unified model seam, client factory consolidation, egress SSRF guards, and caller migrations under `### Changed` and `### Removed`.

## Acceptance Criteria

- [x] Ships `ModelFake` under `tests/support/fakes/model.py` and re-exports in `tests/support/fakes/__init__.py` with `__test__ = False`.
- [x] Implements both `pydantic_ai.models.Model` interface and `LLMClient` duck typing (sync completion, streaming, model listing, deterministic embeddings).
- [x] Contract suite in `tests/test_model_contract.py` validates fake and real implementations (`TestModel`, `LLMClient` over recorded mock frames) offline without network.
- [x] Each test call phase stays under 1.0 s, and all contract and fixture tests pass.
- [x] `create_pydantic_ai_provider` injects `http_client` from the egress factory into pydantic-ai providers accepting it.
- [x] Direct spend tracking in `src/devops_cli/ai/direct.py` attributes provider, server, served-by, tokens, and finish reason across sync, async, and streaming direct requests.
- [x] Retired private `pydantic_ai._run_context` and `_models_by_id` references in `src/devops_cli/ai/`.
- [x] One factory in `src/devops_cli/ai/client/factory.py` builds clients per task.
- [x] `config/settings.py:get_llm_client` is deleted, and `get_llm_client` is re-exported from `devops_cli.ai.client`.
- [x] All inline `LLMClient(...)` constructions in `src/` are routed to `get_llm_client`.
- [x] Conftest fixture `model_fake` registered in `tests/conftest.py` with factory seam integration.
- [x] Migrated existing caller test suites away from internal `LLMClient` patches.
- [x] Changelog fragment `changelog.d/1001.md` added.
- Pending a person: `devops ai chat`, one `devops review path`, and `devops rag query` run against the gateway and against a local Ollama.

## Deliverables

- [x] `tests/support/fakes/model.py`: In-memory `ModelFake`, `ModelCall`, `ModelAnswer`, and `deterministic_embedding`.
- [x] `tests/support/fakes/__init__.py`: Re-export model fake symbols.
- [x] `tests/test_model_contract.py`: 16 contract tests covering fake and real implementations.
- [x] `src/devops_cli/ai/providers/__init__.py`: Inject egress factory HTTP client into providers.
- [x] `src/devops_cli/ai/direct.py`: Rebuilt direct spend tracking with provider/server attribution and streaming spend recording.
- [x] `src/devops_cli/ai/pydantic_ai_bridge.py`: Gateway `served_by` tagging.
- [x] `src/devops_cli/ai/agents/agent.py`: Public `RunContext` import and `get_llm_client` routing.
- [x] `src/devops_cli/ai/agents/context.py`: Public `RunContext` import.
- [x] `src/devops_cli/ai/durable.py`: Retired private `_models_by_id` sync method.
- [x] `src/devops_cli/config/constants.py`: Removed `"direct"` from `CONST_LOCAL_TRANSPORT_LABELS`.
- [x] `src/devops_cli/ai/client/factory.py`: Client factory `get_llm_client`, `build_llm_client`, and `_client_override` seam.
- [x] `src/devops_cli/config/settings.py`: Deleted `get_llm_client`.
- [x] `tests/test_ai_client_factory.py`: Unit tests for factory functions.
- [x] `tests/conftest.py`: Root `model_fake` pytest fixture.
- [x] `tests/test_model_fixture.py`: Comprehensive test suite for `model_fake` fixture and seam.
- [x] `tests/test_instruction_generator.py`: Migrated test away from internal `LLMClient` patch.
- [x] `tests/test_roadmap_refine.py`: Migrated test away from internal `get_llm_client` patch.
- [x] `tests/test_ai_prewarm.py`: Migrated tests away from internal `LLMClient` patch.
- [x] `tests/test_ai_chaos_model.py`: Migrated tests away from internal `LLMClient` patch.
- [x] `tests/test_ai_cmd.py`: Migrated tests away from internal `LLMClient` patches.
- [x] `src/devops_cli/http/egress.py`: Cleaned up private SSRF import.
- [x] `changelog.d/1001.md`: Changelog fragment for #1001.
- [x] `docs/agent/tasks/task-1001-one-model-seam.md`: Task tracking file for #1001.
