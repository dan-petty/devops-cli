# Active Working Log — devops-cli

Chronological log of refactoring milestones, quality gates, and security enhancements.

### [2026-09-05] Native Pydantic AI MCP (`pydantic_ai.mcp`) & Dynamic In-Process FastMCP Toolset Integration
- **Native MCP Toolset Subsystem (`src/devops_cli/ai/mcp/toolset.py`)**:
  - Full native adoption of `pydantic_ai.mcp` API specification:
    - Re-exports all core native classes, protocols, models, and types: `MCPToolset`, `MCPToolsetClient`, `load_mcp_toolsets`, `MCPError`, `Resource`, `ResourceAnnotations`, `ResourceTemplate`, `ServerCapabilities`, `ProcessToolCallback`, `CallToolFunc`, `ToolResult`, `Prompt`, `PromptArgument`, `PromptMessage`, `PromptResult`, `Icon`, `ResourceLink`, `EmbeddedResource`, `ContentBlock`, and `PromptRole`.
    - Implemented high-level domain factories and helpers:
      - `create_devops_mcp_toolset`: Connects a native `pydantic_ai.mcp.MCPToolset` to the in-process `devops-cli` FastMCP server (`devops_cli.ai.mcp.server.mcp`), exposing all 53+ DevOps tools with zero network overhead.
      - `create_mcp_toolset`: Multi-target factory creating toolsets from FastMCP servers, HTTP/SSE/WebSocket URLs, Python script paths, or pre-configured clients, with optional tool prefixing (`PrefixedToolset`).
      - `load_devops_mcp_toolsets`: Multi-format configuration loader for JSON and YAML definitions supporting `${VAR:-default}` environment variable expansion.
- **Dynamic Bridge & Subsystem Integration (`src/devops_cli/ai/tools/mcp_bridge.py`, `src/devops_cli/ai/agents/tools.py`, `src/devops_cli/ai/agents/agent.py`)**:
  - Modernized `mcp_bridge.py`: replaced hardcoded list of 31 tools with dynamic component extraction from FastMCP (`mcp.local_provider._components`), satisfying AGENTS.md rule against incomplete string literal collections. Added `get_devops_mcp_toolset()`.
  - Added `.to_native_toolset()` on `MCPToolset` (`devops_cli.ai.agents.tools`) for seamless bridge between legacy and native toolsets.
  - Enhanced `PydanticAgent` (`agent.py`) to accept union `AgentToolset = AbstractToolset | PyAIAbstractToolset[Any]`, type-safely separating synchronous tool extraction from asynchronous native MCP execution pipelines.
  - Enhanced `create_pydantic_ai_agent` (`devops_cli.ai.pydantic_ai_bridge`) with `toolsets` argument forwarding.
- **Package Re-exports (`devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`, `devops_cli.ai.mcp`, `devops_cli.ai.tools`)**:
  - Re-exported all native MCP types, protocols, and helper functions across all public package tiers with strict typing and comprehensive `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_mcp.py` (10/10 tests passing).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Function Signature (`pydantic_ai.function_signature`) & Tool Interface Introspection
- **Native Function Signature Subsystem (`src/devops_cli/ai/function_signature.py`)**:
  - Full native adoption of `pydantic_ai.function_signature` API specification:
    - Re-exports all core native classes and expressions: `FunctionSignature`, `FunctionParam`, `TypeSignature`, `TypeFieldSignature`, `TypeExpr`, `SimpleTypeName`, `SimpleTypeExpr`, `LiteralTypeExpr`, `GenericTypeExpr`, and `UnionTypeExpr`.
    - Implemented high-level domain adapters:
      - `signature_from_schema`: Constructs `FunctionSignature` directly from JSON Schema definitions with async and description overrides.
      - `signature_from_callable`: Inspects any sync or async Python callable and extracts a `FunctionSignature` using Pydantic AI `Tool` schema generation (automatically stripping internal context dependencies such as `RunContext`).
      - `signature_from_tool`: Universal signature extractor supporting native `pydantic_ai.tools.Tool`, `AgentTool`, duck-typed tools, or raw callables with graceful JSON schema fallback.
      - `get_tool_signatures`: Batch signature extraction across sequences of tool instances or callables.
      - `render_signatures`: Code generation utility that renders clean Python function stubs alongside any referenced `TypedDict` schema definitions with collision detection and disambiguation via `FunctionSignature.get_conflicting_type_names`.
      - `render_tool_interface`: Multi-format interface renderer producing either raw Python stub strings or Markdown-fenced code blocks (`"python"` or `"markdown"`).
- **Subsystem & Agent Integration (`src/devops_cli/ai/agents/tools.py`, `src/devops_cli/ai/agents/agent.py`)**:
  - Enhanced `AgentTool` with `.to_function_signature() -> FunctionSignature` method for immediate introspection into native Pydantic AI signatures.
  - Enhanced `PydanticAgent` with `.get_tool_signatures() -> list[FunctionSignature]` and `.render_tool_interface(*, format="python", include_type_defs=True) -> str` methods for inspecting and rendering all registered agent tools.
- **Package Re-exports (`devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all native function signature types, expressions, and utility adapters across package tiers with comprehensive `__all__` definitions and dynamic module lookups.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_function_signature.py` (15/15 tests passing, 100% code coverage on `src/devops_cli/ai/function_signature.py`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Format Prompt (`pydantic_ai.format_prompt`) & Standardized XML Serialization
- **Native Prompt Formatting Subsystem (`src/devops_cli/ai/format_prompt.py`)**:
  - Full native adoption of `pydantic_ai.format_prompt` API:
    - Re-exports `format_as_xml` directly from `pydantic_ai.format_prompt`.
    - Implemented high-level domain helpers: `format_prompt_data`, `format_context_as_xml`, `format_examples_as_xml`, `format_rag_context_as_xml`, `format_findings_as_xml`, `format_plan_reminder_as_xml`, and `format_metadata_as_xml`.
    - Leveraged Pydantic v2 `Field` metadata extraction (`include_field_info="once"` or `True`) for few-shot examples and structured schemas.
- **Managed Prompt & Subsystem Integration**:
  - Enhanced `ManagedPrompt` (`src/devops_cli/ai/agents/prompt.py`) with `format_xml_variable()` and `render(format_xml_vars=...)` for structured XML variable substitution with boundary sanitization.
  - Modernized `PlanStore` (`src/devops_cli/ai/harness/planning.py`) with `to_xml()` and `format_plan_reminder_as_xml()`.
  - Modernized `format_starting_point_prompt` (`src/devops_cli/ai/response_cache.py`) using `format_as_xml`.
- **Package Re-exports (`devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported `format_as_xml` and all XML formatting helpers with complete `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_format_prompt.py` (15/15 tests passing, 100% coverage on `format_prompt.py`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Exceptions (`pydantic_ai.exceptions`) & Unified Domain Error Taxonomy

- **Native AI Exceptions Subsystem (`src/devops_cli/ai/exceptions.py`)**:
  - Full native adoption of `pydantic_ai.exceptions` API specification:
    - Re-exports all native exception classes: `AgentRunError`, `UserError`, `ModelRetry`, `ToolFailed`, `ApprovalRequired`, `CallDeferred`, `SkipModelRequest`, `SkipToolValidation`, `SkipToolExecution`, `UndrainedPendingMessagesError`, `RunCancelled`, `SuspendedResponseExpired`, `UnexpectedModelBehavior`, `UsageLimitExceeded`, `ConcurrencyLimitExceeded`, `ModelAPIError`, `ModelHTTPError`, `ContentFilterError`, `IncompleteToolCall`, `ToolRetryError`, `ToolFailedError`, and `FallbackExceptionGroup`.
    - Re-exports native warnings: `MessageHistoryMutatedWarning`, `CostCalculationFailedWarning`, `CostNotFoundWarning`, `PydanticAIDeprecationWarning`.
    - Implemented ergonomic utility functions: `is_pydantic_ai_exception(exc)`, `extract_retry_after(exc)`, `extract_cancellation_state(exc)`, `format_pydantic_ai_error(exc)`, and `normalize_to_pydantic_ai_error(exc)`.
- **Domain Error Taxonomy Harmonization (`src/devops_cli/exceptions/ai.py`, `__init__.py`)**:
  - Unified all AI domain exceptions to dual-inherit from both their native Pydantic AI base class and `DevOpsCLIError` (or `LLMInferenceError`), guaranteeing full compatibility with native Pydantic AI engine mechanics while preserving POSIX exit codes and error metadata.
  - Added domain classes: `AgentRunError` (exit 20), `UserError` (exit 21), `ModelAPIError` (exit 22), `ModelHTTPError` (exit 23), `UsageLimitExceeded` (exit 24), `ConcurrencyLimitExceeded` (exit 25), `RunCancelled` (exit 26), `IncompleteToolCall` (exit 27), `SuspendedResponseExpired` (exit 28).
  - Updated `CLIDocumentationGenerator` (`docs/generator.py`) and generated canonical catalog in `docs/ERRORS.md`.
- **Agent & Runner Integration (`src/devops_cli/ai/agents/runner.py`)**:
  - Enhanced `_execute_single_tool` to recognize `ToolFailed` as terminal failure (without consuming retry budget or generating correction prompts) and `SkipToolExecution` as immediate success with provided result.
- **Package Re-exports (`devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all native exception types, helper functions, and warnings with complete `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_exceptions.py` (15/15 tests passing).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Durable Execution (`pydantic_ai.durable_exec`) & Local Workstation Persistence
- **Native Durable Execution Subsystem (`src/devops_cli/ai/durable.py`)**:
  - Full native adoption of `pydantic_ai.durable_exec._base.BaseDurabilityCapability`:
    - Re-exports `BaseDurabilityCapability`, `BoundDurabilityCapability`, `DurabilityError`, `DurableExecutionEvent`, `DurableModelRequestContext`, `DurableModelResponse`, and `DurableToolset`.
    - Implemented workstation-ready `LocalDurabilityCapability` for zero-server durable execution, step recording, and checkpointing for CLI tasks and automated pipelines.
    - Implemented storage backends: `InMemoryStepStore` and `SqliteStepStore` with WAL journaling, thread safety, and resource cleanup.
    - Implemented engine availability checkers and resolvers: `is_temporal_available()`, `is_dbos_available()`, `is_prefect_available()`, `get_available_durable_engines()`, and `resolve_durability_capability(engine, ...)`.
    - Implemented high-level agent factory: `create_durable_pydantic_agent(model, capability, ...)`.
- **Configuration & Defaults Integration (`src/devops_cli/config/settings.py`, `defaults.py`)**:
  - Added `AIDurableConfig` model supporting `enabled`, `engine` (`sqlite`, `memory`, `temporal`, `dbos`, `prefect`), `store_path`, `task_queue`, and `workflow_prefix`.
  - Added defaults: `DEFAULT_AI_DURABLE_ENGINE = "sqlite"`, `DEFAULT_AI_DURABLE_STORE_PATH`, `DEFAULT_AI_DURABLE_TASK_QUEUE`, `DEFAULT_AI_DURABLE_WORKFLOW_PREFIX`.
- **StepPersistence Harmonization (`src/devops_cli/ai/agents/persistence.py`)**:
  - Refactored `StepPersistence` to use storage models from `durable.py` and added `to_durability_capability()` bridging to `LocalDurabilityCapability`.
- **Package Re-exports (`devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all durable execution classes, helpers, and types with complete `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_durable.py` (14/14 tests passing, >94% code coverage on `src/devops_cli/ai/durable.py`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).


### [2026-09-05] Native Pydantic AI Direct Requests (`pydantic_ai.direct`) & Invocation Optimization
- **Native Direct Model Request Subsystem (`src/devops_cli/ai/direct.py`)**:
  - Full native adoption of `pydantic_ai.direct` API specification:
    - Re-exports `model_request`, `model_request_sync`, `model_request_stream`, `model_request_stream_sync`, and `StreamedResponseSync`.
    - Implemented high-level ergonomic functions: `direct_model_request`, `direct_model_request_sync`, `direct_model_request_stream`, and `direct_model_request_stream_sync` with automatic model resolution via `resolve_pydantic_ai_model`, concurrency limits, and OpenTelemetry instrumentation (`pydantic_ai.direct.*`).
    - Implemented message normalization helper `to_model_messages` supporting raw strings, `ChatMessage` lists, and native `ModelMessage` objects.
    - Implemented response extractors: `extract_response_text`, `extract_response_thinking`, and `to_llm_response` adapter.
- **Unified Client Integration (`src/devops_cli/ai/client/unified.py`)**:
  - Added native direct request methods to `LLMClient`: `direct_request`, `direct_request_sync`, `direct_stream`, and `direct_stream_sync`.
- **Package Re-exports (`devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all direct model request primitives, types, and helpers with complete `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_direct.py` (14/14 tests passing, 100% code coverage on `src/devops_cli/ai/direct.py`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green.

### [2026-09-05] Native Pydantic AI Concurrency (`pydantic_ai.concurrency`) & Model-Level Concurrency Wrappers
- **Native Concurrency Subsystem (`src/devops_cli/ai/concurrency.py`)**:
  - Direct integration with native Pydantic AI concurrency primitives per Pydantic AI API specification:
    - Re-exports `AbstractConcurrencyLimiter`, `ConcurrencyLimiter`, `ConcurrencyLimit`, `AnyConcurrencyLimit`, `ConcurrencyLimitExceeded`, `ConcurrencyLimitedModel`, `limit_model_concurrency`, `get_concurrency_context`, and `normalize_to_limiter`.
    - Implemented thread-safe shared limiter registry (`get_shared_concurrency_limiter` and `get_model_concurrency_limiter`) for orchestrating model inference capacity across agents and pipeline stages.
    - Implemented `track_concurrency_slot` context manager helper.
- **Bridge & Multi-Agent Architecture Integration (`src/devops_cli/ai/pydantic_ai_bridge.py`, `agent.py`, `pipeline.py`)**:
  - `resolve_pydantic_ai_model`: added optional `model_concurrency: AnyConcurrencyLimit = None` parameter, automatically wrapping resolved models via `limit_model_concurrency(model, model_concurrency)`.
  - `create_pydantic_ai_agent` and `get_persona_pydantic_agent`: added support for `max_concurrency` and `model_concurrency` parameters, passing concurrency limits to both native `pydantic_ai.Agent` and `devops_cli.ai.agents.agent.PydanticAgent`.
  - `PydanticAgent`: added `max_concurrency: AnyConcurrencyLimit = None` with normalized `self._concurrency_limiter`, wrapped asynchronous calls in `run_async` and `run_stream_async` with `get_concurrency_context(self._concurrency_limiter, f"agent:{self.name}")`.
  - `MultiAgentPipeline`: added `concurrency_limit: AnyConcurrencyLimit = None` with `self.concurrency_limiter`, and implemented `run_parallel_async` with cooperative limiter backpressure.
- **Package Re-exports (`src/devops_cli/ai/__init__.py`, `agents/__init__.py`, `agents/pydantic_agent.py`)**:
  - Full re-exports and `__all__` definitions for all concurrency types and functions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_concurrency.py` (10/10 tests passing, 100% code coverage on `src/devops_cli/ai/concurrency.py`).
  - Full CI validation suite (`uv run devops ci`): 10/10 checks green (test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Common Tools (`pydantic_ai.common_tools`) & Embedding Config Retention
- **Native Common Tools & TypedDict Schemas (`src/devops_cli/ai/common_tools.py`)**:
  - Bridged and re-exported native Pydantic AI common tools (`pydantic_ai.common_tools`) with robust enterprise SSRF protection and zero-dependency fallbacks.
  - Implemented TypedDict result schemas conforming to native Pydantic AI: `WebFetchResult`, `DuckDuckGoResult`, `TavilySearchResult`, `ExaSearchResult`, `ExaAnswerResult`, `ExaContentResult`.
  - Re-exported native tool classes and subagents: `ImageGenerationTool`, `ImageGenerationSubagentTool`, `ImageGenerationFallbackModel`, `XSearchTool`, `XSearchSubagentTool`, `XSearchFallbackModel`, `DuckDuckGoSearchTool`, `TavilySearchTool`, `WebFetchLocalTool`, `ExaSearchTool`, `ExaToolset`.
  - Maintained zero-trust egress security: `web_fetch_tool` rejects private, loopback, and link-local IP addresses (`_is_private_or_loopback`) and validates post-redirect destination hostnames.
- **Native Toolsets & Agent Facade Re-exports (`src/devops_cli/ai/agents/pydantic_agent.py`, `agents/__init__.py`, `ai/__init__.py`)**:
  - Re-exported native toolsets from `pydantic_ai.toolsets`: `ApprovalRequiredToolset`, `CombinedToolset`, `DeferredLoadingToolset`, `DynamicToolset`, `ExternalToolset`, `FilteredToolset`, `FunctionToolset`, `IncludeReturnSchemasToolset`, `PrefixedToolset`, `PreparedToolset`, `RenamedToolset`, `SetMetadataToolset`, `WrapperToolset`.
  - Re-exported all native common tools and schemas across `devops_cli.ai.agents` and `devops_cli.ai` packages with complete `__all__` definitions.
- **Embedding Configuration Retention & Model Tag Preservation (`src/devops_cli/ai/agents/embeddings.py`, `src/devops_cli/ai/rag/embeddings.py`)**:
  - Resolved root cause of vector dimension drift between 1024 and 768:
    - Fixed `Embedder._get_engine` to inherit active configuration from `load_settings().ai` instead of defaulting to unconfigured `AIConfig()` (`localhost:11434` and `qwen3-embedding:0.6b` 1024-dim).
    - Fixed model name parsing in `Embedder`: replaced destructive `.split(":")[-1]` with `.removeprefix("ollama:").removeprefix("openai:")`, preserving model tags like `embeddinggemma:300m`.
    - Fixed `EmbeddingsEngine` and `OllamaEmbeddingModel` to inherit active settings from `load_settings().ai` and prioritize task overrides `ai.tasks.embedding.model`.
- **Quality Gates & Test-First Verification**:
  - Authored `tests/test_embedding_config_retention.py` (4/4 tests passing) verifying config retention, Ollama tag preservation, and task overrides.
  - Authored `tests/test_native_common_tools.py` (10/10 tests passing) verifying TypedDict schemas, native tool exports, SSRF blocking, and agent re-exports.
  - Authored `tests/test_pydantic_ai_native_capabilities.py` (9/9 tests passing) verifying dual compatibility between native `pydantic_ai.Agent` and `devops_cli.ai.agents.agent.PydanticAgent`.
  - Full static typing verification with strict mypy targeting Python 3.14 across all 288 source files in `src/`.

### [2026-09-05] Common AI Hallucinations External JSON Catalog, Ground Truth Safety & Autonomous Management
- **JSON Catalog Externalization & Separation (`src/devops_cli/ai/review/common_hallucinations.json`, `common_hallucinations.py`)**:
  - Extracted built-in common hallucinations catalog from inline Python definitions into a dedicated declarative JSON resource (`common_hallucinations.json`).
  - Implemented dynamic loading in `_build_builtin_hallucinations()` with safe error handling and fallback parsing.
  - Exported `CONST_HALLUCINATIONS_FILE_NAME` and `DEFAULT_HALLUCINATIONS_FILE_PATH` across `devops_cli.config` and `devops_cli.ai.review`.
- **Strict Ground-Truth Safety Guards & Invariant Enforcement**:
  - Enforced strict safety invariant: common English words (such as `"secret"`, `"token"`, `"key"`, `"test"`, `"error"`, `"syntax"`, `"code"`, `"mutable"`, etc.) are declared in `_FORBIDDEN_COMMON_WORDS` and strictly blocked from contributing to similarity matching or auto-recording.
  - Real defects, genuine syntax errors, and valid security vulnerabilities are protected from false-positive hallucination tagging.
  - Implemented `verify_ground_truth_hallucination` requiring concrete AST or file inspection (e.g. verifying `ast.parse` for syntax claims or checking placeholder tokens in source) before any finding can be matched as a hallucination.
- **Verification Pipeline & CLI Integration**:
  - Connected `is_common_hallucination` and `verify_ground_truth_hallucination` into `_deterministic_pre_verification` in `src/devops_cli/ai/review/verification.py`.
  - Integrated `auto_record_invalidated_finding` across syntax check invalidations, line boundary checks, LLM verification rejections, and manual CLI invalidation in `devops ai review verify`.
- **Strategic Roadmap Multi-Tier Scrutiny (`docs/ROADMAP.md`)**:
  - Updated `docs/ROADMAP.md` under `v0.2.10 - Active Release` with multi-tier scrutiny architecture:
    - Tier 1: Deterministic AST/Parser Ground-Truth Pre-Gating ($\ge 0.80$ similarity).
    - Tier 2: Confidence Penalties & Multi-Agent Adversarial Debate ($0.40 \le s < 0.80$).
    - Tier 3: Automated Negative Few-Shot Prompt Guardrail Mutation.
- **Comprehensive Quality Gates & Testing**:
  - Authored 13 unit tests in `tests/test_common_hallucinations.py` validating JSON loading, persistence, similarity calculations, forbidden words exclusion, and real vulnerability protection.
  - Full `devops ci` quality gate passed cleanly (10/10 checks: 100% test pass, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

- **Safe Dictionary Access & Result Key Aliasing (`src/devops_cli/commands/rag.py`, `src/devops_cli/ai/rag/indexer.py`)**:
  - Fixed `KeyError: 'files_indexed'` in `devops ai rag index` (`index_cmd`) and `index-kb` (`index_kb_cmd`) by using safe `.get()` accessors with fallbacks across `indexed_files` / `files_indexed`, `total_chunks` / `chunks_indexed`, and `removed_files` / `pruned_chunks`.
  - Normalized `WorkspaceIndexer.index_workspace` and `WorkspaceIndexer.index_knowledge_base` return dictionaries to supply both canonical (`indexed_files`, `total_chunks`, `removed_files`) and alias keys (`files_indexed`, `chunks_indexed`, `pruned_chunks`), guaranteeing 100% backward and forward compatibility for all consumers and tests.
- **Verification & Quality Gate**:
  - Authored test `test_rag_index_cmd_handles_canonical_indexer_keys` in `tests/test_rag_cli.py` reproducing the KeyError and verifying clean resolution.
  - All 10 `devops ci` quality gates passing cleanly.

### [2026-09-05] Dynamic Embedding Vector Dimension Resolution & Elimination of Lookup Table
- **Dynamic Embedding Vector Dimension Resolution (`src/devops_cli/ai/rag/embeddings.py`)**:
  - Completely eliminated the brittle model-name substring matching table (`_infer_default_dimension`) in accordance with `AGENTS.md` guidelines against incomplete string literal collections.
  - Implemented dynamic active endpoint probing (`_probe_dimension`):
    - Queries active Ollama node (`/api/embed`) with a minimal probe sample (`["probe"]`) to measure the model's actual vector dimension directly from the running inference engine.
    - If `/api/embed` is unavailable, queries `/api/show` to extract model architecture parameters (`model_info["*.embedding_length"]`).
    - For OpenAI/Copilot endpoints, queries `/embeddings` with probe input to determine actual dimension.
  - Implemented dynamic runtime dimension observation: records `self._dimension = len(embs[0])` on any successful embedding call.
  - Added module-level `_MODEL_DIMENSION_CACHE` keyed by `(provider, model)` to avoid redundant probe calls across `EmbeddingsEngine` instances.
  - Unified default offline/disconnected fallback dimension to standard `DEFAULT_DRY_RUN_EMBEDDING_DIMENSION` (768) without any model-name guessing heuristics.
  - Simplified Ollama endpoint URL resolution via shared helper `_get_ollama_urls()`.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test specifications in `tests/test_rag_embeddings.py`:
    - `test_dynamic_probe_ollama_embed`: Validates dynamic probe via `/api/embed`.
    - `test_dynamic_probe_ollama_show_metadata`: Validates dynamic dimension inspection via `/api/show` `model_info`.
    - `test_dynamic_probe_openai_embeddings`: Validates dynamic probe via OpenAI `/embeddings`.
    - `test_runtime_dimension_cache_and_learning`: Validates runtime dimension observation and cross-instance caching.
    - `test_deterministic_fallback_embeddings`: Validates offline fallback behavior without lookup table substring matching.
  - Full `devops ci` quality gate passed cleanly (10/10 checks: tests, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Qdrant Collection Dimension Auto-Recreation & Warning Deduplication
- **Automatic Vector Dimension Detection & Migration (`src/devops_cli/ai/rag/qdrant.py`)**:
  - Connected `ensure_collection` into `upsert_points` to inspect payload vector dimensions before upserting batches.
  - Automatically detects vector dimension mismatches against existing Qdrant collections (e.g. 768 vs 1024), deletes the incompatible collection, and recreates it with the required vector dimension without crashing.
  - Implemented in-memory verified collection dimension caching (`_verified_collections`) to eliminate redundant round-trips for subsequent batches.
  - Deduplicated dimension mismatch warnings in `search_points` (`_dim_mismatch_warned`) so that background code reviews log at most once per collection rather than repeating on every reviewed file.
- **Verification & Quality Gate**:
  - Authored unit tests in `tests/test_rag_qdrant.py` verifying collection recreation on dimension change and warning deduplication.
  - All 10 `devops ci` quality gates passed cleanly (100% test pass, coverage >= 90%).

### [2026-09-05] Review Findings Remediation (Session `20260905-003105`), Python 3.14 PEP 758 Awareness & Review Loop Hardening

- **Codebase Findings Remediation (Session `20260905-003105`)**:
  - **Concurrent Background Process Ceiling (`src/devops_cli/ai/harness/shell.py`)**: Added `max_bg_processes: int = 10` cap to `Shell` and `start_command`, blocking concurrent process unbounded growth.
  - **Command Argument Traversal & Denylist (`src/devops_cli/ai/harness/shell.py`)**: Blocked `..` traversal in arguments and enhanced denied commands prefix matching for `mkfs.*`, `reboot`, `shutdown`, `poweroff`.
  - **Kubernetes Apply Manifest SSRF & Traversal Defense (`src/devops_cli/commands/k8s/cluster_context.py`)**: Added URL scheme (`http`/`https`), loopback/private IP (`127.0.0.1`, `169.254.169.254`), and local filesystem traversal validation (`..`) to `kubectl apply`.
  - **Vault Address Validation (`src/devops_cli/security/vault_broker.py`)**: Enforced `http`/`https` scheme check and traversal sequence validation on `vault_addr`.
  - **Prompt Injection Tag Neutralization (`src/devops_cli/ai/agents/prompt.py`)**: Added `_PROMPT_INJECTION_TAGS_REGEX` in `ManagedPrompt.render` to scrub `<system>`, `<instructions>`, `<prompt>`, and `<untrusted>` tags from substituted variables.
  - **Web Fetch Tool Post-Redirect SSRF Protection (`src/devops_cli/ai/common_tools.py`)**: Added post-redirect host validation against private/loopback/link-local addresses in `web_fetch_tool`.
  - **Diff Memory Ceiling (`src/devops_cli/ai/diff/difftastic.py`)**: Added `MAX_DIFF_TEXT_CHARS = 500_000` ceiling in `sanitize_diff_output`.
  - **LangChain Tool Adapter Traversal Defense (`src/devops_cli/ai/ext_langchain.py`)**: Added `_validate_langchain_kwargs` checking path/file arguments for traversal sequences in `tool_from_langchain`.
  - **Macroscope Base Ref Validation & Playwright Scheme Enforcement (`src/devops_cli/ai/harness/agents.py`)**: Validated `diff_base` ref in `Macroscope` against traversal sequences and constrained `PlaywrightBrowser.navigate` to `http`/`https` schemes.
  - **Model Bundler Output Directory Validation (`src/devops_cli/ai/model_bundler.py`)**: Added traversal and system directory containment validation to `bundle_ollama_models`.
  - **Kubernetes Pod Diagnostics Secret Masking (`src/devops_cli/commands/k8s/diagnostics.py`, `sanitization.py`)**: Masked exception messages in `_build_pods_table` using `_sanitize_output_text` and enhanced `_SECRET_PATTERNS` to catch token/secret labels.
  - **Pipeline Path & Function Name Validation (`src/devops_cli/commands/pipeline.py`)**: Enforced file existence check on `pipeline_path` and identifier safety validation on `function_name`.
  - **Async Coroutine Support in CodeMode (`src/devops_cli/ai/harness/os_access.py`, `tools.py`)**: Added `__call__` to `AgentTool` and coroutine-awaiting support in `CodeMode._make_sandboxed_tool_wrapper`.
- **Review Engine & Self-Improvement Loop Hardening**:
  - **Strict Location Canonicalization & Noise Filtering (`src/devops_cli/ai/review_schema.py`)**: Updated `canonicalize_finding_location` to reject non-alphanumeric tokens, markdown asterisks (`**`), section headers (`###`), and non-path tokens.
  - **Conversational Praise & Approval Scrubbing (`src/devops_cli/ai/review_schema.py`)**: Added `_APPROVAL_PREFIX_REGEX` and `_PRAISE_PREFIX_REGEX` in `sanitize_finding_text` to strip leading praise ("Good. But ...") and filter pure approvals ("The function uses ... Good.") from review findings.
  - **Finding Emptiness Detection (`src/devops_cli/ai/review_schema.py`)**: Updated `Finding.is_empty` and added `title` to `_clean_text_fields` to automatically discard findings with conversational approval or invalid locations.
  - **Prompt Task Definitions & Knowledge Base Synchronization**:
    - Updated `verify_finding_system.md` and `review_output_instruction.md` with explicit Python 3.14 PEP 758 modern syntax awareness (`except E1, E2:`) and zero-praise rules in structured finding lists.
    - Synchronized `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md` and generated all CLI docs and README via `devops docs generate --sync-readme`.
- **Quality Gates & Test-First Verification**:
  - Authored 20 new test specifications integrated into canonical domain test suites (`test_prompt_programmatic_functions.py`, `test_review_verification.py`, `test_harness.py`, `test_k8s_context.py`, `test_vault_broker.py`, `test_ai_agent_prompt.py`, `test_common_tools.py`, `test_difftastic.py`, `test_ext_langchain.py`, `test_model_bundle.py`, `test_k8s_logs_diff_chaos.py`, `test_load_and_pipeline.py`) — 100% passing.
  - Verified full `devops ci` quality gate: all 10 checks passed cleanly (1,487 tests passed, 90.69% code coverage).


### [2026-09-04] Review Findings Remediation, Prompt Leakage Defense & Closed-Loop Review Engine Hardening
- **Codebase Findings Remediation (Session `20260904-192102`)**:
  - **Path Traversal Prefix Collision (`src/devops_cli/ai/harness/filesystem.py`)**: Fixed `_resolve_safe_path` using `resolved.is_relative_to(root_res)` rather than prefix string matching to prevent sibling-directory breakout attacks.
  - **Repomap Symlink & File Size Guards (`src/devops_cli/ai/repomap.py`)**: Added symlink skipping (`not source_file.is_symlink()`), strict root containment validation, and 5MB per-file size guard (`MAX_REPOMAP_FILE_SIZE_BYTES`).
  - **Reporting Session Containment (`src/devops_cli/ai/review/stages/reporting.py`)**: Added path traversal sequence detection (`..`) and containment verification against allowed review base directories.
  - **Static Scan Boundary Containment & Concurrency (`src/devops_cli/ai/review/stages/static_scan.py`)**: Added boundary containment checks in `_resolve_target_path` and thread-safe list synchronization via `Lock()` for concurrent analyzer appends.
  - **Agent Tool Argument Validation (`src/devops_cli/ai/agents/context.py`, `capabilities.py`)**: Hardened `_check_path_traversal` against relative traversal sequences and sanitized `NativeTool` generic tool configurations to avoid leaking tokens in model settings.
  - **Vault Path Validation (`src/devops_cli/commands/vault.py`)**: Added `_validate_vault_path` checking for empty paths, `..` traversal sequences, and invalid control characters across `vault get`, `set`, and `sync`.
  - **Telemetry SSRF & Network Topology Masking (`src/devops_cli/server/routes/telemetry.py`)**: Implemented `_sanitize_telemetry_endpoint` to mask private IP addresses and bounded probe connection timeouts to 0.5s.
  - **Docker Workload Sandbox Timeout Enforcement (`src/devops_cli/docker/sandbox.py`)**: Added configurable `timeout: float = 300.0` in `WorkloadSandboxConfig` and passed `timeout=int(self.config.timeout)` to `container.wait()`.
  - **Kubernetes OpenWebUI Credential Sourcing (`src/devops_cli/commands/k8s/stack_lifecycle.py`)**: Added `_get_openwebui_bootstrap_credentials()` reading credentials securely from environment variables (`OPENWEBUI_ADMIN_EMAIL`, `OPENWEBUI_ADMIN_PASSWORD`).
  - **Console Output Sanitization (`src/devops_cli/output/console.py`)**: Integrated `_sanitize_output_text` into `print_dry_run_result`.
- **Review Engine & Self-Improvement Loop Hardening**:
  - **Prompt Leakage & Conversational Scratchpad Defense (`src/devops_cli/ai/review_schema.py`)**: Hardened `canonicalize_finding_location` to scan for embedded file paths with line ranges and reject conversational scratchpad text or prompt instructions, while preserving canonical locations and target specifiers (`file:start-end`, `file:resource`, `lockfile:package`). Hardened `sanitize_finding_text` with `_SCRATCHPAD_PREFIX_REGEX` to strip chain-of-thought deliberation sentences.
  - **Verification Index Alignment (`src/devops_cli/ai/review/verification.py`)**: Aligned LLM verification response parsing strictly to unresolved candidate findings, eliminating index mapping skews when earlier findings are deterministically invalidated.
  - **Deterministic Syntax Hallucination Elimination (`src/devops_cli/ai/review/verification.py`)**: Generalized `_check_syntax_error_hallucination` to invalidate false-positive syntax error claims across language-agnostic parsers (`ast`, `json`, `yaml`, `tomllib`), including Python 3.14 PEP 758 unparenthesized multi-exception syntax.
- **Prompt Task Definitions & Knowledge Base Synchronization**:
  - Hardened `review_output_instruction.md`, `verify_finding_system.md`, `diff_review_prompt.md`, and `path_review_prompt.md` with strict prohibitions against chain-of-thought leakage in structured JSON fields and explicit PEP 758 modern syntax awareness.
  - Synchronized `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md` and regenerated all CLI documentation and README references via `devops docs generate --sync-readme`.
- **Quality Gates & Test Coverage Expansion**:
  - Created 38 new unit tests across `tests/test_findings_remediation.py`, `tests/test_review_loop_hardening.py`, `tests/test_vault_cmd.py`, and `tests/test_k8s_runtime_cmd.py` (100% pass rate).
  - Elevated `src/devops_cli/commands/vault.py` coverage from 40.82% to 100% and `src/devops_cli/commands/k8s/cluster_runtime.py` to 100%.
  - Executed full `devops ci` quality gate with 10/10 green checks (1,467+ tests passing cleanly).

---

### [2026-09-03] Release v0.2.9 Prompt Rule Transformation, False Invalidation Removal & Legacy Cleanup
- **Deterministic Prompt Rule Transformations & Location Canonicalization (`src/devops_cli/ai/review_schema.py`, `tests/test_prompt_programmatic_functions.py`)**:
  - Implemented pure programmatic functions replacing fragile inline LLM prompt heuristics: `canonicalize_finding_location` (canonical `file:start-end` or `file:line` formatting, markdown reference stripping, inverted range correction), `sanitize_finding_text` (stripping criteria leakage and prompt boilerplate), and `derive_recommendation` (severity-based merge decision mapping).
  - Authored comprehensive test suite in `tests/test_prompt_programmatic_functions.py` with 100% pass rate.
- **Review Finding Feedback Dataset Export & Self-Improvement Loop**:
  - Exported verified finding dataset to `.data/feedback_dataset.jsonl` (319 records) enabling downstream agentic self-improvement and prompt fine-tuning.
- **Removal of Functions That Invalidate Valid Findings or Validate Invalid Findings**:
  - Removed heuristic auto-invalidation functions (`_check_contextual_exemption`, `_check_kustomization_namespace_exemption`, `_check_iac_operational_outputs`, `_check_missing_symbol_hallucination`, `_check_syntax_error_hallucination`, `_check_line_boundaries`) from `src/devops_cli/ai/review/verification.py` to prevent suppressing valid security defects.
  - Fixed verification default to `verified=False` preventing unverified findings from falsely validating.
  - Removed synthetic criteria count ratio scoring in finding verification.
  - Refined adversarial debate invalidation to preserve valid findings mentioning dependencies like `httpx2`.
  - Removed blanket exclusion instructions from `guardrails_isolation.md` and `verify_finding_system.md`.
- **Legacy & Shim Code Elimination**:
  - Removed legacy sequential single-prompt embedding fallback (`_fetch_fallback_single_embeddings`) in `src/devops_cli/ai/rag/embeddings.py`.
  - Cleaned up obsolete v0.1.1 feature comments and stubs in `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, and `src/devops_cli/config/options.py`.
  - Updated review CLI docstrings to eliminate vestigial version tags.
- **Defense-in-Depth Path Traversal & SSRF Hardening**:
  - Enforced `allow_traversal=False` default in `validate_path` (`src/devops_cli/core/validation.py`).
  - Added DNS rebinding resolution to `_is_private_or_loopback` in `src/devops_cli/ai/common_tools.py`.
  - Added secret and credential token redaction (`***REDACTED***`) across agent hooks in `src/devops_cli/ai/agents/persistence.py`.
  - Added directory traversal guards to SQLite step store and symlink boundary containment guards across `aibom.py`, `kubeconform.py`, `skills.py`, and `pre_analysis.py`.
  - Sanitized prompt template variables in `ManagedPrompt.render` (`src/devops_cli/ai/agents/prompt.py`).


### [2026-09-02] Release v0.2.9 Universal Stage Pipelines, Async HTTP/2 Connection Broker & Local K8s Chaos Runner
- **Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`, `tests/test_pipeline_engine.py`)**:
  - Implemented `StagePipeline[ContextT, ResultT]` and `PipelineStage` framework supporting sequential and DAG-based stage execution with scratchpad context sharing, early termination guards, and metrics recording.
- **Unified Async HTTP/2 Connection & Security Broker (`src/devops_cli/http/broker.py`, `tests/test_http_broker.py`)**:
  - Implemented `HttpClientBroker` managing shared `httpx2` client connection pools with HTTP/2 multiplexing, exponential backoff retries, SSRF private network isolation, and automatic traceparent propagation.
- **Local Kubernetes Chaos & Fault Injection Runner (`src/devops_cli/k8s/chaos_runner.py`, `tests/test_k8s_chaos_runner.py`)**:
  - Implemented `ChaosFaultRunner` supporting declarative pod disruptions, recovery time observation, and automatic rollback handling.
- **Continuous IDE File Watcher & Instant Review (`devops ai review path --watch`)**:
  - Added `--watch` / `-w` and `--debounce-ms` options to `devops review path` leveraging `DebouncedFileWatcher` to trigger instant multi-persona reviews on active file changes.
- **Automated Kubernetes Stack Credential Synchronization (`src/devops_cli/k8s/credentials.py`, `devops k8s sync-secrets`)**:
  - Implemented zero-plaintext password extraction from Kubernetes cluster secrets (`argocd-initial-admin-secret`, `kube-prometheus-stack-grafana`, `grafana`) directly into OS Keyring (`argocd_password`, `grafana_password`).
  - Integrated automated credential synchronization into `devops k8s deploy-stack` and `devops k8s sync-secrets`.
- **Automated Dependency Vulnerability Remediation PR Engine (`src/devops_cli/security/dependency_remediator.py`, `devops scan fix`)**:
  - Implemented `DependencyRemediator` automating CVE patching across lockfiles (`uv lock --upgrade-package`), dry-run remediation planning, and git topic branch staging (`fix/security-<cve>`).
  - Registered `scan_fix` FastMCP tool for autonomous agent-driven dependency remediation.
- **Isolated Dockerized Workload Sandbox Environment (`src/devops_cli/docker/sandbox.py`, `devops test sandbox`, `devops docker sandbox`)**:
  - Implemented `WorkloadSandboxRunner` providing rootless, ephemeral container test harnesses with bound workspace directories, resource quotas (`--memory`, `--cpus`), network isolation (`--network none`), and automatic container teardown.
  - Registered `docker_sandbox` FastMCP tool.
- **Enterprise HashiCorp Vault & Cloud KMS Secret Broker (`src/devops_cli/security/vault_broker.py`, `devops vault`)**:
  - Implemented `VaultSecretBroker` supporting Vault KV-v2 REST engine, URI references (`vault://<path>#<key>`), zero-plaintext storage, and seamless fallback to OS Keyring.
  - Added `devops vault` subcommands (`status`, `get`, `set`, `sync`) and registered `vault_status` and `vault_get` FastMCP tools.
- **Kubernetes Background Port-Forward Daemon Management (`src/devops_cli/k8s/port_forward_daemon.py`, `devops k8s port-forward`)**:
  - Implemented `PortForwardDaemonManager` with managed PID lifecycle tracking (`.data/k8s/port_forwards.json`), status inspection (`devops k8s port-forward-status`), and graceful process termination (`devops k8s port-forward-stop`).


### [2026-09-02] Release v0.2.8 Output Subsystem Deconstruction, Language Localization & Complexity Elimination
- **Output Subsystem Modularization (`src/devops_cli/output/formatters/`)**:
  - Deconstructed monolithic `formatter.py` into dedicated submodules: `scalars.py`, `tables.py`, and `panels.py`.
  - Re-exported all formatters via `devops_cli.output` with zero breaking changes, enforcing high-level public formatting methods project-wide.
- **Language Localization & Centralized Messages (`src/devops_cli/lang/en/messages.py`)**:
  - Added `BadgeMessages` and `OutputMessages` dataclasses to `LanguageCatalog` for full localization of terminal badges, status indicators, finding headers, and Kubernetes node states.
- **Declarative Dispatch Tables & Cyclomatic Complexity Elimination**:
  - Refactored AST symbol streaming in `src/devops_cli/ai/ast_stream.py` to use table-driven `_NODE_HANDLERS` dictionary and recursive decorator extraction.
  - Implemented declarative `_NATIVE_TOOL_SETTINGS_BUILDERS` and `_extract_local_tools` in `src/devops_cli/ai/agents/capabilities.py`.
  - Decoupled sub-agent execution in `src/devops_cli/ai/harness/workflow.py` via `_invoke_agent_callable`.
  - Replaced procedural truncation in `src/devops_cli/ai/harness/compaction.py` with `_TRUNCATION_FORMATTERS` and `_apply_compactor`.
  - Simplified settings coercion in `src/devops_cli/config/settings.py` via `_coerce_setting_value`.
  - Consolidated certificate source loading in `src/devops_cli/crypto/tls_certificates.py` via `_read_cert_bytes`.
- **Zombie Code & Legacy Shims Elimination**:
  - Removed obsolete shims: `src/devops_cli/ai/review/rendering.py`, `src/devops_cli/models/dry_run.py`, and `src/devops_cli/core/dry_run.py`.
  - Merged `SSHKeyInfo` into `src/devops_cli/models/ssh.py` and deleted redundant `src/devops_cli/models/github.py`.
  - Cleaned duplicate entries in `src/devops_cli/output/__init__.py::__all__`.
- **Quality Gate**: Verified 10/10 quality gates via `devops ci` (1,328 unit tests, strict mypy across 275 source files, ruff, bandit, pip-audit, actionlint, docs).

### [2026-09-01] Release v0.2.7 Model Curation AIBOM, AST Streaming, Re-Ranking & Synthesis Protocol
- **AI Bill of Materials (AIBOM) Generator & Model Curation (`src/devops_cli/security/aibom.py`, `src/devops_cli/commands/scan.py`, `tests/test_aibom.py`)**:
  - Implemented `devops scan aibom` generating CycloneDX 1.5-compliant AI Bill of Materials manifests from workspace and model repositories.
  - Implemented dynamic serving hardware heuristic estimator calculating peak RAM, inference VRAM, and storage for dense and MoE models across quantization bit depths.
  - Added automated `trust_remote_code` AST and configuration scanner detecting unverified remote execution scripts prior to GPU provisioning.
- **Zero-Allocation AST Symbol & Token Stream Parser (`src/devops_cli/ai/ast_stream.py`, `tests/test_ast_stream.py`)**:
  - Implemented generator-based streaming parser yielding structural symbols (classes, functions, async methods, imports, decorators) with zero intermediate full-tree allocations.
  - Added line-level token stream parser detecting indentation depths, comments, and string literals.
- **Cross-Encoder Context Re-Ranker & Deep Semantic RAG (`src/devops_cli/ai/rag/reranker.py`, `tests/test_rag_reranker.py`)**:
  - Implemented `CrossEncoderReranker` evaluating full query-chunk cross-token interaction density and reciprocal positional discounting for RAG context retrieval.
- **"Big Decides, Small Types, Big Checks" Synthesis Protocol (`src/devops_cli/ai/agents/synthesis_protocol.py`, `tests/test_synthesis_protocol.py`)**:
  - Implemented three-stage multi-agent synthesis pipeline orchestrating frontier planning models, local fast drafting models, and frontier auditor models.
- **High-Performance Streaming Serializers (`src/devops_cli/output/streaming_serializer.py`, `tests/test_streaming_serializer.py`)**:
  - Added low-memory streaming serializers for JSON arrays (`stream_json_array`), line-delimited JSON (`stream_jsonl`), and multi-document YAML (`stream_yaml_docs`).
- **SSH Key Prefix Configuration & Options Across Subcommands (`src/devops_cli/commands/ssh.py`, `src/devops_cli/crypto/ssh_keys.py`, `tests/test_ssh.py`)**:
  - Enhanced `devops ssh register`, `rotate`, `status`, and `list` with `--prefix` / `-p` option and connected key lookup and GitHub title generation to `settings.ssh.key_prefix`.
- **Quality Gate**: Verified 10/10 quality gates via `devops ci` (1,277 unit tests, strict mypy across 275 source files, ruff, bandit, pip-audit, actionlint, docs).

### [2026-08-31] Release v0.2.6 AI Model Routing & Governance, Live Watchers, Complexity Analysis & SBOM
- **Multi-Dimensional AI Model Routing & Governance (`src/devops_cli/ai/router.py`, `tests/test_ai_router.py`)**:
  - Dynamic multi-axis model routing across task complexity, freshness, and data sensitivity.
- **AST Code Complexity & SBOM Generation (`src/devops_cli/security/complexity.py`, `src/devops_cli/security/sbom.py`, `src/devops_cli/commands/scan.py`)**:
  - Added `devops scan complexity` and `devops scan sbom`.
- **Live Resource & State Watchers Across Subsystems (`src/devops_cli/watchers/live_resource.py`, `src/devops_cli/commands/`)**:
  - Added `--watch` / `-w` across `devops k8s pods`, `devops docker stats`, `devops argo cd apps list`, and `devops release status`.

### [2026-08-31] Release v0.2.5 Code Library Manuals, Centralized Catalogs & PydanticAI MCP Enhancements
- **Dedicated Code Library Knowledge Base Suite (`src/devops_cli/ai/knowledge_base/devops_cli/libraries/`)**:
  - Authored 23 comprehensive architectural reference manuals covering all production dependencies and development quality tools with official project links, comparable alternatives analysis, key concepts, and common usage examples.
  - Linked all library guides in `src/devops_cli/ai/knowledge_base/README.md` and `python_packages.md`.
- **PydanticAI Model Context Protocol (MCP) Client & Sampling Protocol (`devops_cli.ai.agents.tools`, `devops_cli.ai.agents.agent`)**:
  - Implemented `sampling_model`, `client_info`, `http_client` (custom TLS/SSL context), and `sse_read_timeout` across `MCPToolset`.
  - Added dynamic `.model` property and `set_mcp_sampling_model()` to `PydanticAgent` enabling downstream MCP servers to request client-side LLM completions.
- **Centralized Help Catalog & Command Alignment (`devops_cli.lang.en.help`, `devops_cli.commands`)**:
  - Centralized CLI option and argument help strings into `devops_cli.lang.en.help.HELP`.
  - Fixed `repomap_cmd`, `k8s_check_deprecated`, and `enable_tls_stack` to eliminate ad-hoc imports and align with canonical Finding models.
- **Quality Gate**: Verified full quality gate (`devops ci`), strict mypy clean (269 source files), 100% test pass.

### [2026-08-27] Release v0.2.4 Architecture & Threat Modeling Synthesis, Trace Waterfall Profiling & RAG Retrieval
- **Trace Waterfall Visualizer CLI (`devops telemetry profile`, `devops_cli.telemetry.tracer`)**:
  - Implemented interactive terminal waterfall breakdown and latency heatmap of OpenTelemetry spans with trace ID filtering.
- **Aider-Style AST Repository Map Generator (`devops ai repomap`, `devops_cli.ai.repomap`)**:
  - Added whole-repository AST symbol and relationship map generator parsing classes, functions, signatures, and docstrings without context overflow.
- **Architecture & Threat Modeling Diagram Synthesis (`devops ai diagram`, `devops_cli.ai.diagram`)**:
  - Implemented automated Mermaid architecture topology (`graph TD`) and STRIDE zero-trust threat flowcharts (`graph LR`).
- **Automated Unit Test Synthesizer (`devops ai test-gen`, `devops_cli.ai.test_gen`)**:
  - Added automated test generation for AST-analyzed symbols and uncommitted diffs.
- **FastMCP Tool Schema Contract Regression Suite (`tests/test_fastmcp_contracts.py`)**:
  - Added contract verification suite across 40+ FastMCP tools verifying typed signatures and parameter documentation.

### [2026-08-26] Release v0.2.3 Parameter Defaults & Invariant Constants Architecture
- **Centralized Defaults & Invariant Constants (`devops_cli.config.defaults`, `devops_cli.config.constants`)**:
  - Centralized all static defaults, timeouts, and paths into `config/defaults.py` and `config/constants.py`.
- **Declarative Subprocess Command Builders (`devops_cli.config.commands`)**:
  - Standardized declarative builders for kubectl, kustomize, bandit, trivy, popeye, kubelinter, pluto, uv-audit, tf, and tofu.
- **Declarative Output Renderable Models (`devops_cli.output.models`)**:
  - Implemented Pydantic v2 schemas (`TablePayload`, `PanelPayload`, `MarkdownPayload`, `SyntaxPayload`, `RulePayload`, `KeyValuePayload`) with encapsulated Rich console rendering.
- **Domain Exception Taxonomy (`devops_cli.exceptions`)**:
  - Standardized strongly typed exceptions inheriting from `DevOpsCLIError` with canonical POSIX exit codes and machine-readable error codes.

### [2026-08-25] Release v0.2.2 Checkov IaC Security, TFLint Cloud Linter & Dive Docker Analysis
- **Checkov IaC Static Policy & Compliance Engine (`devops scan iac`, `devops scan checkov`)**:
  - Added static compliance and policy security auditing across Terraform, CloudFormation, Kubernetes, and Dockerfile manifests.
- **TFLint Cloud Provider Linter (`devops tf lint`)**:
  - Added static Terraform/OpenTofu validation against cloud provider rules and module constraints.
- **Dive Docker Layer Efficiency Analyzer (`devops docker analyze-layers`)**:
  - Added container image layer exploration and wasted space efficiency analysis.
- **Kubeconform Fast OpenAPI Schema Validator (`devops k8s validate`)**:
  - Added offline Kubernetes manifest validation against OpenAPI JSON schemas supporting arbitrary target versions.

### [2026-08-24] Release v0.2.1 Multi-Persona Code Review Calibrated Feedback & RAG Vector Indexing
- **PydanticAI Multi-Agent Pipeline Orchestrator (`devops_cli.ai.agents`)**:
  - Implemented typed `PydanticAgent` framework with toolsets, memory, streaming, and execution hooks.
- **Qdrant Vector Database Integration & RAG Engine (`devops ai rag`, `devops_cli.ai.rag`)**:
  - Implemented local on-disk vector database storing dense embeddings of knowledge base task manuals and target architecture docs.
- **OpenTofu & Terraform IaC Automation (`devops tf`, `devops tofu`)**:
  - Implemented complete IaC lifecycle commands (`init`, `plan`, `apply`, `output`, `state`, `validate`).

### [2026-08-23] Release v0.2.0 Pydantic v2 Migration & Full Async Architecture
- **Pydantic v2 Core Migration**:
  - Upgraded entire model catalog to Pydantic v2 with `model_validate`, `model_dump`, and `Field(default_factory=...)`.
- **Async Streaming Unified LLM Client (`devops_cli.ai.llm.client`)**:
  - Migrated LLM client to HTTP/2 async connection pooling with real-time reasoning token streaming.

### [2026-08-22] Release v0.1.13 Embedding Benchmarks, TLS Automation & OpenTelemetry Observability
- **Embedding Model Benchmark Suite (`devops ai benchmark --type embedding`, `devops_cli.ai.benchmark`)**:
  - Implemented specialized vector embedding evaluation engine (`EmbeddingBenchmarkRunner`) measuring Recall@1, Recall@3, MRR, Cosine Margin, single-query latency (p50/p95 ms), batch throughput (items/sec and chars/sec), and vector dimension/$L_2$ norm health.
  - Curated 15 domain-specific evaluation pairs + 10 distractors across Security, Kubernetes, Architecture, CI/CD, and Infrastructure.
  - Added CLI auto-detection routing for embedding models (`nomic-embed-text`, `qwen3-embedding`, `all-minilm`, `bge-*`, `text-embedding-3-*`).
- **Local & Homelab TLS Certificate Management (`devops tls`, `devops cert`, `devops_cli.crypto`)**:
  - Implemented CA and TLS server/client certificate issuance with SAN extensions for IP addresses, hostnames, localhost, `.lan`/`.local` domains, and Kubernetes service FQDNs.
  - Implemented automated Kubernetes TLS secret provisioning (`devops tls inject-k8s-secret`, `devops k8s enable-tls`) and cert-manager ClusterIssuer integration.
- **Universal OpenTelemetry Integration (`devops telemetry`, `devops otel`, `devops_cli.telemetry`)**:
  - Integrated OTLP distributed trace exporters across all CLI commands and AI multi-agent pipeline stages with Jaeger collector manifests (`k8s/otel/jaeger.yaml`).
- **Standard Library & PEP 508 Code Hygiene Refactoring (`devops_cli.security.reference_extractor`)**:
  - Eliminated arbitrary string lists/blacklists; adopted standard `ast`, `tokenize`, `packaging.requirements.Requirement`, `tomllib`, `json`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, and `tldextract`.
  - Implemented PEP 508/PEP 621/PEP 735 requirement extraction, Python AST literal/comment tokenization, and RFC 2606 reserved domain exclusions.
- **Review Pipeline Optimization & Prompt Hardening**:
  - Bounded linked file graph resolution to top 10 relevant files with universal standard library import filtering (`_UNIVERSAL_MODULES`).
  - Hardened review and verification prompts (`src/devops_cli/ai/tasks/review.md`, `verify_finding.md`).
- **Quality Gate**: Verified full test suite (522 unit tests passed, 100% green), ruff lint clean, ruff format clean, strict mypy clean (140 source files), documentation synchronized.

### [2026-08-20] Release v0.1.12 Enhancements & Open Source Modernization
- **Official `qdrant-client` SDK Adoption**: Replaced handcrafted HTTP REST calls with the official `qdrant-client` SDK for vector database operations, enabling connection pooling, typed vector search (`query_points`), and batch upserts.
- **Hierarchical Configuration with `pydantic-settings`**: Migrated `Settings` to inherit from `pydantic_settings.BaseSettings` with `SettingsConfigDict(env_prefix="DEVOPS_CLI_", env_nested_delimiter="__")`.
- **Multi-Context & Remote Cluster Kubernetes Support (`devops k8s`)**: Added dynamic cluster reachability verification (`_cluster_reachable`) supporting remote k3s, EKS, and GKE cluster contexts via `kubectl cluster-info`, with `--context` (`-c`) support across all lifecycle commands and automatic iterative pre-existing Helm resource adoption (`_adopt_helm_resource_if_conflict`).
- **Multi-GPU Native Ollama DaemonSet Deployment**: Consolidated the LLM stack to deploy `k8s/llm/ollama-daemonset.yaml` directly as a native manifest with `NVIDIA_VISIBLE_DEVICES: "all"`, `runtimeClassName: nvidia`, hostPort 11434, and shared NFS model cache.
- **Code Review Finding Remediation & Prompt Hardening**: Remediated findings from session `20260820-011920` (path traversal defenses, tool description sanitization against prompt injection, version & label regex validations, telemetry query masking), hardened review prompts against syntax hallucinations, and exported 1,842 benchmark findings to `.data/feedback.jsonl`.
- **Quality Gate**: Verified full test suite (419 unit tests passed), ruff lint clean, ruff format clean, strict mypy clean (109 source files), bandit security scan clean.
- **Automated Release Cycle Suite (`devops release`)**: Implemented complete release subcommands suite (`status`, `prepare`, `check`, `notes`, `tag`) automating version bumping across `pyproject.toml` and `__init__.py`, updating `CHANGELOG.md`, and executing authoritative release verification.
- **FastMCP Server Release Integration**: Added `release_status` MCP tool enabling AI agents to inspect version consistency, git tags, and documentation freshness over Model Context Protocol.
- **Automated Documentation Introspection Engine (`devops docs`)**: Built dynamic Typer/Click introspection system generating markdown reference manuals (`CLI_REFERENCE.md`, `MCP_TOOLS.md`, `ENV_VARS.md`) and syncing the `README.md` Complete Command Matrix (`devops docs generate --sync-readme`, `devops docs check`).
- **Principal SRE Architecture & Governance Blueprint**: Created comprehensive [`ARCHITECTURE.md`](../ARCHITECTURE.md) (system topology, multi-agent sequence flow, FastMCP bridge, DevContainer lifecycle, security perimeter), standard MIT [`LICENSE`](../LICENSE), enterprise [`SECURITY.md`](../SECURITY.md), and SRE [`CONTRIBUTING.md`](../CONTRIBUTING.md).
- **CI/CD Quality Gates & Release Automation**: Created GitHub Actions workflows (`.github/workflows/ci.yml`, `.github/workflows/release.yml`) for 7-gate quality validation and automated tag publishing.
- **Centralized Constants & Defaults**: Unified all static paths, timeouts, regex patterns, and user-facing messages into `config/constants.py`, `config/defaults.py`, and `lang/en.py`.
- **Quality Gate**: Verified full test suite (300 unit tests passed), ruff lint clean, ruff format clean, strict mypy clean (93 source files), bandit security scan clean.

### [2026-08-14] AI Review Persona Tuning, Finding Verification & Self-Improvement Loop Hardening

- **Feedback & Invalidation Benchmark Loop**: Analyzed and exported invalidated review findings into `.data/feedback_dataset.jsonl` benchmark dataset; identified primary false-positive patterns (hallucinated Python 2 multi-exception syntax, non-existent file paths, pre-submission placeholder redactions, and historical research/evidence documents).
- **Universal Review Task Prompt Hardening**: Refined `src/devops_cli/ai/tasks/review.md` and `personas/devsecops/prompt.md` with explicit validation rules: distinguishing active code from historical research/evidence packs (`evidence/`, `docs/LOG.md`, `KNOWN_ISSUES.md`), requiring rigorous excerpt verification before reporting syntax bugs, respecting pre-submission redaction placeholders (`<masked-*>`, `[REDACTED]`, `${{ secrets.* }}`), and enforcing actionable fix structures.
- **Verification Engine Guardrails**: Enhanced finding verification system prompt (`_VALIDATION_SYSTEM` in `verification.py`) to systematically validate file/line existence, verify language syntax against target runtime standards, and filter false positives with explicit invalidation justifications.
- **Cross-Repo Code & Tool Hardening**: Addressed high-value findings across tools and docs generators (`tools/apidrift/acknowledge.py`, `suggest.py`, `scanner.py`, `scripts/generate_metrics_docs.py`, `generate_config_docs.py`, `generate_endpoints_docs.py`, `.github/actions/report-drift/action.yml`, Helm templates, and Makefile targets).
- **Quality Gate**: Verified full test suite (2268 tests in `meraki-dashboard-exporter` passed, `devops-cli` review & persona tests passed), ruff lint clean, ruff format clean, mypy clean, and `make docgen` clean.

### [2026-08-13] Kubernetes LLM Stack Expansion (`devops k8s *-stack`)
- **LLM Stack Definition**: Added `llm` stack comprising Ollama local inference server (`values-ollama.yaml`), Open-WebUI interface (`values-open-webui.yaml`), Qdrant vector database (`values-qdrant.yaml`), and Valkey in-memory cache (`valkey.yaml`).
- **Multi-Stack Orchestration**: Enhanced `devops k8s deploy-stack`, `devops k8s teardown-stack`, `devops k8s bootstrap`, `devops k8s port-forward`, and `devops k8s configure-urls` with `--stack [infra|llm|all]` option.
- **FastMCP Tool Integration**: Updated FastMCP tools `k8s_deploy_stack` and `k8s_teardown_stack` to accept optional `stack: str = "infra"`.
- **Test Coverage**: Added comprehensive test cases for LLM and multi-stack lifecycle, dry-run responses, and validation error handling in `tests/test_k8s.py`.

### [2026-08-13] Release v0.1.7 Implementation & Completion
- **Native DevContainer Lifecycle Engine**: Implemented `devops devcontainer run-lifecycle` (`post_create_lifecycle`, `post_start_lifecycle`) in pure Python replacing legacy shell scripts (`postCreate.sh`, `postStart.sh`).
- **Enhanced AI Scratchpad Buffer**: Integrated `ScratchpadBuffer` in multi-persona agentic review orchestrator to retain reasoning state across multi-turn diff reviews.
- **Prompt Token & Latency Optimization**: Streamlined JSON schema serialization (`separators=(",", ":")`) and context packing to maximize inference responsiveness.
- **Worker Error Resilience & Storage Standardization**: Hardened parallel review pipeline exception handling and centralized all metadata under `.data/`.
- **Test Isolation & Dry-Run Fixtures**: Added autouse fixture `reset_dry_run_state` in `tests/conftest.py` ensuring clean dry-run environment isolation across xdist test workers.
- **Quality Gate**: Executed `devops ci` — 269 passed, ruff lint clean, ruff format clean, strict mypy clean, bandit security clean, uv audit clean.

### [2026-08-12] Release v0.1.6 SecOps & Security Integrations
- **Aqua Trivy Static Scanner**: Added `devops scan [repo|image|iac]` and finding injection into `devsecops` persona review payloads.
- **Red Hat Kube-linter Auditor**: Added `devops k8s lint` static manifest and Helm chart security analysis.
- **Derailed Popeye Cluster Sanitizer**: Added `devops k8s audit` active cluster health scanner.
- **Fairwinds Pluto API Checker**: Added `devops k8s check-deprecated` Kubernetes API deprecation scanner.

### [2026-08-12] Release v0.1.5 Minikube Service Auto-Config & 7-Gate CI
- **Minikube Endpoint Auto-Detection**: Implemented `devops k8s configure-urls` auto-detecting NodePort endpoints for ArgoCD, Grafana, and Prometheus.
- **FastMCP Tool Alignment**: Verified and mapped 18 FastMCP tools across repository, Kubernetes, Docker, and workspace resources.
- **7-Gate Quality Gate**: Expanded CI pipeline to 7 sequential gates (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).

### [2026-08-12] Release v0.1.4 Implementation & Completion
- **Default AI Metadata Analysis**: Made `--enhanced` mode default across `devops ai analyze` subcommands (`path`, `branch`, `pr`), generating 6-10 line minimalist pseudocode structural outlines, complexity scores, and ISO `last_analyzed` timestamps. Added `--no-enhanced` flag for basic metadata opt-out.
- **Incremental Analysis Caching**: Implemented `st_mtime` vs `last_analyzed` caching to skip redundant LLM calls on unchanged files, with `--update-all` (`-u`) flag to force full metadata regeneration.
- **Submodule-Aware Dependency Scanner**: Preserved full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`) in Python AST and package analysis.
- **Clean Pseudocode Generation**: Eliminated generic boilerplate language and strictly excluded import statements and package directives from pseudocode output to ensure clean separation from extracted dependencies.
- **Dry-Run & Helper Standardization**: Centralized Pydantic dry-run rendering in `dry_run/state.py`, git origin URL parsing in `core/repo.py`, and LLM client instantiation in `config/settings.py`.
- **Quality Gate**: Executed `devops ci` — 215 passed, ruff lint clean, ruff format clean, strict mypy clean, uv audit clean.

### [2026-08-11] Release v0.1.3 Implementation & Completion
- **Interactive Patch Staging**: Added `--interactive / -i` to `devops ai review apply-patch` for diff previews.
- **Air-Gapped Model Bundler**: Added `devops ai bundle-models` command (`bundle_ollama_models`).
- **Kubernetes RBAC Audit Policy**: Added `devops k8s rbac-audit` command for overprivileged access auditing.
- **SIEM Live Audit Streamer**: Added `devops config audit-stream` command (`stream_audit_records`).
- **Quality Gate**: Executed `devops ci` — 214 passed, ruff lint clean, ruff format clean, strict mypy clean, uv audit clean.

### [2026-08-11] Release v0.1.3 Planning
- **v0.1.3 Implementation Plan**: Formulated plan for interactive patch application (`apply-patch --interactive`), air-gapped model bundling (`bundle-models`), Kubernetes RBAC auditing (`rbac-audit`), and live SIEM audit streaming.

### [2026-08-11] Release v0.1.2 Implementation & Completion
- **Multi-Cluster Kubeconfig Management**: Added `devops k8s switch-context` for active cluster context management.
- **SIEM Audit Trail Logger**: Integrated `AuditLogger` (`record_audit_event`) streaming execution events to `.data/logs/audit.jsonl`.
- **Automated Fix Patch Application**: Added `devops ai review apply-patch` subcommand to stage suggested LLM code fixes.
- **Subcommand Dry-Run Models**: Standardized Pydantic dry-run responses across `argo`, `grafana`, `prometheus`, `devcontainer`.
- **Quality Gate**: Executed `devops ci` — 211 passed, ruff lint clean, ruff format clean, strict mypy clean, uv audit clean.

### [2026-08-11] Release v0.1.2 Planning
- **v0.1.2 Implementation Plan**: Formulated plan for multi-cluster Kubeconfig context management (`devops k8s context`), SIEM audit trail logging (`AuditLogger`), automated patch application prep (`apply-patch`), and dry-run model expansion.

### [2026-08-11] Release v0.1.1 Implementation & Completion
- **Feedback Dataset Exporter**: Added `devops ai review export-feedback` command (`export_invalidated_feedback`) to export false-positive review findings into JSONL benchmark datasets.
- **Custom Team Personas**: Implemented `load_custom_repo_persona` to discover and load team prompt overrides defined in `.devops/personas/<name>.md`.
- **Headless CI Keyring Auth**: Added `devops config auth-headless` and `_EPHEMERAL_CI_SECRETS` memory fallback for DBus-less headless CI runners.
- **Line-Level PR Inline Comments**: Added `create_pr_review_comment` to `GitHubClient`.
- **Quality Gate**: Executed `devops ci` — 208 passed, ruff lint clean, ruff format clean, strict mypy clean, uv audit clean.

### [2026-08-11] Release v0.1.0 & v0.1.1 Planning
- **v0.1.0 Release**: Shipped codebase metadata analysis (`devops ai analyze`), structured Pydantic model dry-run outputs, modular `devops_cli.dry_run` package, `devops ci audit` dependency scanning (`uv audit`), `UV_MALWARE_CHECK=1` devcontainer environment, and centralized `LanguageCatalog` literals.
- **v0.1.1 Implementation Plan**: Formulated roadmap for line-level GitHub PR inline comments (`--post-inline`), human invalidation benchmark exporter (`export-feedback`), repository-level custom team personas (`.devops/personas/`), and headless CI auth fallback (`auth-headless`).
- **Quality Gate**: Executed `devops ci` — 201 passed, ruff lint clean, ruff format clean, strict mypy clean, uv audit clean.

### [2026-08-10] AI Review Prompt Injection Defenses & Boundary Sanitization
- **Tag Sanitization**: Implemented `_sanitize_prompt_boundary_tags()` in `commands/review.py` to escape closing XML tags in reviewed content.
- **Untrusted Input Framing**: Wrapped diffs, source files, segment summaries, excerpts, and findings in XML boundary tags (`<untrusted_code_diff>`, `<target_code_to_review>`, etc.).
- **System Prompt Security Directives**: Added prompt isolation guardrails to `_persona_system_prompt()` and enclosed repo `AGENTS.md` in `<project_conventions_context>` tags.
- **Task Prompt Directives**: Updated `review.md`, `compose.md`, `metadata.md`, and `verify_finding.md` with prompt material and indirect injection guardrails.
- **Quality Gate**: Executed `devops ci` — 148 passed, ruff lint clean, ruff format clean, strict mypy clean.

### [2026-08-10] Environment Variable Specification Command (`devops config output`)
- **Config Output Subcommand**: Added `devops config output` (aliases `env`, `env-vars`) in `commands/config.py` supporting Rich Table, `--export`, and `--json`.
- **Specification Metadata**: Added `EnvVarSpec` and `get_all_env_var_specs()` in `config/env.py` covering all 30 environment variables.
- **Quality Gate**: Executed `devops ci` — 141 passed, ruff lint clean, ruff format clean, strict mypy clean.

### [2026-08-10] DevSecOps Hardening & Fast Static Metadata Extraction
- **Python 2 Remediation**: Fixed legacy `except Err1, Err2:` syntax across 7 files.
- **Path Traversal Guards**: Enforced `_is_safe_workspace_path` across `read_file`, `list_files`, `devops ai review path`, and `devops workspace add`.
- **Fast Metadata Extraction**: Replaced 34+ sequential LLM network calls with deterministic static analysis (`SegmentMeta`) upfront in <5ms.
- **Quality Gate**: Executed `devops ci` — 136 passed, ruff lint clean, ruff format clean, strict mypy clean.
