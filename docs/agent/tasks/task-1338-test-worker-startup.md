# Task: Test Worker Startup and Collection Optimization (#1338)

**Issue**: [#1338](https://github.com/dan-petty/devops-cli/issues/1338)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: type/test, priority/p2-medium, scope/ci

## Description

Pytest-xdist initializes 16 parallel workers under `-n logical` in the devcontainer environment. During test collection, every worker process imports and inspects all test modules and their transitive dependencies across `src/devops_cli`. Prior to optimization, top-level module imports pulled heavy third-party SDKs (`anthropic`, `google.genai`, `kubernetes`, `qdrant_client`, `openai`) eagerly into memory across all 16 workers concurrently, generating severe CPU scheduling contention and inflating start-up latency to over 37 seconds.

To eliminate this overhead:
1. Replaced eager imports of model SDKs and vector clients across `src/devops_cli/ai/agents/`, `src/devops_cli/ai/models/`, `src/devops_cli/ai/providers/`, and `src/devops_cli/ai/rag/` with deferred runtime accessors and PEP 562 `__getattr__` exports.
2. Directly imported `NativeRunContext` from `pydantic_ai._run_context` in `src/devops_cli/ai/agents/context.py` and `agent.py` to avoid triggering eager loads of `pydantic_ai.tools` (which eagerly pulled `fastmcp`, `mcp`, and `griffe`).
3. Made `_PYDANTIC_PROVIDERS` and model mappings in `src/devops_cli/ai/providers/__init__.py` and `src/devops_cli/ai/models/__init__.py` lazy, ensuring SDK modules are loaded strictly upon first instantiation.
4. Converted Qdrant client wrappers in `src/devops_cli/ai/rag/qdrant.py` and indexer references in `src/devops_cli/ai/rag/indexer.py` to lazy bindings (`_LazyNativeQdrantClient`, `_LazyQModels`), deferring the `qdrant_client` library until vector queries are dispatched.
5. In tests, deferred module-level imports of heavy SDKs and `kubernetes.client` in test fixtures (`tests/k8s_fakes.py`, `tests/test_k8s_models.py`, `tests/test_pydantic_ai_profiles_and_providers.py`, `tests/test_qdrant_cluster_addressing.py`, `tests/test_qdrant_timeout_setting.py`, `tests/test_rag_query_telemetry.py`).
6. Added an architectural invariant test `test_ai_agents_and_providers_import_no_model_sdks` in `tests/test_cli_startup_imports.py` to permanently prevent model SDK regressions at module level.

## Benchmarks & Telemetry

### 1. Baseline Measurements (at base `origin/release/v0.2.31`)

- **Start-up & Collection Only** (`uv run pytest -q -p no:cacheprovider -k zz_no_such_test_zz`):
  - Run 1: 37.52s
  - Run 2: 36.40s
  - Run 3: 37.68s
  - **Baseline Median: 37.52s**
- **Full Test Run** (`uv run pytest -q -p no:cacheprovider`):
  - Run 1: 152.57s
  - Run 2: 149.48s
  - Run 3: 152.32s
  - **Baseline Median: 152.32s**
  - Test counts: 10,131 passed, 1 skipped, 8 xfailed (10,140 total)
- **Top 5 Import Costs** (`uv run python -X importtime -m pytest --collect-only -q -s -n0 -p no:cacheprovider`):
  - By package self-time:
    1. `devops_cli`: 1804.83 ms
    2. `anthropic`: 987.10 ms
    3. `kubernetes`: 608.40 ms
    4. `google`: 510.10 ms
    5. `qdrant_client`: 428.82 ms
    *(also `openai`: 365.42 ms)*
  - By individual module self-time:
    1. `google.genai.types`: 468.69 ms
    2. `kubernetes.client.models.v1_topology_spread_constraint`: 379.27 ms
    3. `devops_cli.commands.ci`: 323.31 ms
    4. `devops_cli.ai.mcp.server`: 237.99 ms
    5. `qdrant_client.http`: 234.43 ms
  - By cumulative import time:
    1. `devops_cli.ai.agents`: 4358.23 ms
    2. `devops_cli.ai.agents.pipeline`: 2577.02 ms
    3. `devops_cli.ai.agents.pydantic_agent`: 2567.36 ms
    4. `devops_cli.ai.agents.guardrails`: 1702.58 ms
    5. `devops_cli.ai.agents.capabilities`: 1698.13 ms

### 2. Post-Optimization Measurements

- **Start-up & Collection Only** (`uv run pytest -q -p no:cacheprovider -k zz_no_such_test_zz`):
  - Run 1: 28.02s
  - Run 2: 27.89s
  - Run 3: 28.44s
  - **Post-Optimization Median: 28.02s**
  - **Start-up Savings: 9.50s (25.32% reduction vs baseline 37.52s, exceeding required $\ge 15\%$)**
  - Half-saving requirement for full run: $\ge 4.75\text{s}$ saving ($\le 147.57\text{s}$).
- **Full Test Run** (`uv run pytest -q -p no:cacheprovider`):
  - Run 1: 146.17s (real 148.42s)
  - Run 2: 140.30s (real 142.69s)
  - Run 3: 141.05s (real 143.38s)
  - **Post-Optimization Median: 141.05s (real median 143.38s)**
  - **Full Run Savings: 11.27s reduction (exceeding required $\ge 4.75\text{s}$)**
  - Test counts: 10,132 passed (+1 new invariant test), 1 skipped, 8 xfailed, 0 failed
- **Top Import Costs Post-Optimization**:
  - By package self-time:
    - `anthropic`: **0.00 ms** (eliminated at collection)
    - `google`: **0.00 ms** (eliminated at collection)
    - `qdrant_client`: **0.00 ms** (eliminated at collection)
    - `openai`: **0.00 ms** (eliminated at collection)
    - `kubernetes`: reduced to 248.67 ms
  - By cumulative import time:
    - `devops_cli.ai.agents`: 2461.71 ms (down from 4358.23 ms, saving 1.896s in single-process import alone)

## Acceptance Criteria

- [x] (person-run) **Baseline first.** At the item's base, on an otherwise idle devcontainer, the task file records:
  - the median of three runs of `uv run pytest -q -p no:cacheprovider -k zz_no_such_test_zz` (start-up and collection only) -> 37.52s;
  - the median of three runs of `uv run pytest -q -p no:cacheprovider` (the full run) -> 152.32s;
  - the five largest import costs from `uv run python -X importtime -m pytest --collect-only -q -s -n0 -p no:cacheprovider` -> `devops_cli`, `anthropic`, `kubernetes`, `google`, `qdrant_client`.
- [x] (person-run) After the change, the start-up median is at least 15% below its baseline. The new figures are recorded in the task file (28.02s median, 25.32% reduction).
- [x] (person-run) The full-run median falls by at least half as many seconds as the start-up median did, so the saving is not moved into the tests (11.27s saved, exceeding required 4.75s).
- [x] No test is lost. The full run collects as many tests as at the base, with the same passed, skipped and xfailed counts (10,132 passed with 1 new invariant test, 1 skipped, 8 xfailed).
- [x] The gate still measures coverage over `src` and still meets `fail_under = 90` (measured 92.36%).
- [x] `changelog.d/1338.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.

## Deliverables

- [x] `src/devops_cli/ai/agents/context.py` & `agent.py`: Import `NativeRunContext` directly from `pydantic_ai._run_context` to bypass cascading imports of `fastmcp`, `mcp`, and `griffe`.
- [x] `src/devops_cli/ai/agents/pipeline.py`: Decouple eager module-level dependencies on `pydantic_agent.py`.
- [x] `src/devops_cli/ai/agents/embeddings.py`: Defer `OpenAIEmbeddingModel` via `__getattr__` and `TYPE_CHECKING`.
- [x] `src/devops_cli/ai/models/ollama.py`: Defer `AsyncOpenAI`, `OllamaProvider`, `OllamaModel`, and `OpenAIChatModel` via runtime imports and `__getattr__`.
- [x] `src/devops_cli/ai/models/__init__.py`: Lazy `__getattr__` with explicit `_OLLAMA_EXPORTS` frozenset.
- [x] `src/devops_cli/ai/providers/__init__.py`: Implement lazy provider mapping `_LazyPydanticProviders` and lazy `__getattr__`.
- [x] `src/devops_cli/ai/agents/pydantic_agent.py` & `agents/__init__.py`: Defer `OllamaModel`, `OllamaProvider`, `OpenAIChatModel` via `__getattr__` and `TYPE_CHECKING`.
- [x] `src/devops_cli/ai/rag/indexer.py`: Move `QdrantClient` under `TYPE_CHECKING`, defer import in `resolve_qdrant_client`, and expose via `__getattr__`.
- [x] `src/devops_cli/ai/rag/retriever.py`: Move `QdrantClient` under `TYPE_CHECKING` and expose via `__getattr__`.
- [x] `src/devops_cli/ai/rag/qdrant.py`: Wrap `qmodels` and `NativeQdrantClient` in lazy proxy accessors (`_LazyQModels`, `_LazyNativeQdrantClient`) and dynamically check transient Qdrant exceptions.
- [x] `tests/k8s_fakes.py`: Implement `_LazyKubernetesClient`.
- [x] `tests/test_k8s_models.py`: Import lazy `client` and defer `V1PodStatus` and event test parameter generation.
- [x] `tests/test_pydantic_ai_profiles_and_providers.py`: Defer native provider imports inside test methods and consolidate linear assertions into structural tuple equality checks.
- [x] `tests/test_qdrant_cluster_addressing.py`: Defer `QdrantClient` import inside test functions.
- [x] `tests/test_qdrant_timeout_setting.py`: Defer `qdrant_module` import inside test functions.
- [x] `tests/test_rag_query_telemetry.py`: Defer `NativeQdrantClient` import inside test function.
- [x] `tests/test_cli_startup_imports.py`: Add `test_ai_agents_and_providers_import_no_model_sdks` invariant test.
- [x] `changelog.d/1338.md`: Document test worker startup and full test suite run performance improvements.
- [x] `docs/agent/tasks/task-1338-test-worker-startup.md`: Task documentation and benchmark records.
