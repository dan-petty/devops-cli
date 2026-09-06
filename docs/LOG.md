# Active Working Log — devops-cli

Chronological log of refactoring milestones, quality gates, and security enhancements.

### [2026-09-06] FastMCP Server Expansion, Tool Parity & Pydantic AI MCP Integration Validation
- **FastMCP Server Expansion to 72 Registered Tools**:
  - Added 19 missing tools bringing full parity with all core CLI subcommands:
    - Security scanning: `scan_trivy`, `scan_gitleaks`, `scan_semgrep`, `scan_checkov`, `scan_complexity`, `scan_aibom`, `scan_sbom`.
    - Kubernetes resilience & audit: `k8s_chaos`, `k8s_audit`, `k8s_lint`, `k8s_validate`, `k8s_diff_helm`.
    - HashiCorp Vault enterprise secrets: `vault_set`, `vault_sync`.
    - AI benchmarking & architecture analysis: `benchmark_embeddings`, `ai_architecture`.
    - Git & PR governance: `branches_list`, `pr_list`, `pr_checks`.
  - All tools strictly enforce zero nesting depth > 5, complexity <= 10, argument validation (`_validate_mcp_arg`), and defensive timeouts.
- **FastMCP Prompt Templates & Dynamic System Resources**:
  - Implemented 4 prompt templates via `@mcp.prompt()`: `code_review_prompt`, `security_audit_prompt`, `k8s_diagnostics_prompt`, `architecture_analysis_prompt`.
  - Implemented 2 additional dynamic system resources: `resource://vault/status` (live Vault health and sealing) and `resource://mcp/tools` (live tool catalog).
- **Submodule Re-Export & IDE Integration**:
  - Fully re-exported all 72 tools, 4 prompts, 6 resources, and Pydantic AI toolset types in `src/devops_cli/ai/mcp/__init__.py`.
  - Added `devops mcp export-schemas` CLI command to export JSON schemas directly into `/home/vscode/.gemini/antigravity-ide/mcp/devops-cli/`.
- **Documentation & Test Verification**:
  - Regenerated `docs/MCP_TOOLS.md` and `README.md` via `devops docs generate --sync-readme`.
  - Updated `tests/test_fastmcp_contracts.py`, `tests/test_mcp.py`, and `tests/test_pydantic_ai_mcp.py` verifying contracts, execution, and Pydantic AI MCPToolset discovery.

### [2026-09-06] Codebase Stylistic & Structural Drift Remediation & Development Parameters
- **Architectural Invariant Enforcement & Quality Gate Integration**:
  - Authored `tests/test_architectural_invariants.py` asserting strict adherence to architectural standards across the codebase:
    - Zero functions or methods with nesting depth $> 5$ across all of `src/devops_cli`.
    - Cyclomatic complexity $\le 10$ for complex tool factories (`FileSystem.get_tools`).
    - Zero bare Python built-in exceptions (`ValueError`, `RuntimeError`, `TypeError`) raised in domain logic.
    - Mandatory inheritance of all domain exceptions from `DevOpsCLIError`.
    - Test collection hygiene (`__test__ = False` on dummy/mock models).
- **Domain Exception Taxonomy Expansion**:
  - Added canonical error codes in `src/devops_cli/config/constants.py`: `CONST_ERROR_CODE_VAULT`, `CONST_ERROR_CODE_DOCKER_SANDBOX`, `CONST_ERROR_CODE_K8S`, `CONST_ERROR_CODE_MODEL_BUNDLE`, `CONST_ERROR_CODE_HARNESS`.
  - Created strongly typed domain exceptions inheriting from `DevOpsCLIError` and standard Python exception types:
    - `src/devops_cli/exceptions/vault.py`: `VaultError`, `VaultKeyError`, `VaultConfigurationError`, `VaultOperationError`.
    - `src/devops_cli/exceptions/k8s.py`: `KubernetesError`, `KubernetesContextError`, `ChaosExecutionError`, `KubernetesDeployError`.
    - `src/devops_cli/exceptions/docker.py`: `DockerError`, `DockerSandboxError`.
    - `src/devops_cli/exceptions/ai.py`: `ModelBundleError`, `HarnessValidationError`, `HarnessExecutionError`.
  - Re-exported new exception classes through `src/devops_cli/exceptions/__init__.py` and updated `docs/ERRORS.md`.
- **Bare Generic Exception Remediation (22 Modules)**:
  - Replaced bare `ValueError` and `RuntimeError` with strongly typed domain exceptions across:
    - Docker sandbox (`sandbox.py`)
    - Kubernetes chaos runner (`chaos_runner.py`)
    - Kubernetes cluster context (`cluster_context.py`)
    - Vault broker & CLI (`vault_broker.py`, `commands/vault.py`)
    - AI model bundler & durable sessions (`model_bundler.py`, `durable.py`)
    - AI harness subsystems (`skills.py`, `workflow.py`, `planning.py`, `shell.py`, `memory.py`, `os_access.py`, `compaction.py`).
- **Nesting Depth & Cyclomatic Complexity Reductions**:
  - Refactored high indentation hotspots to $\le 4$ levels project-wide:
    - `toolsets/__init__.py`: Flattened `extract_tools_from_toolset` and `get_instructions`.
    - `providers/__init__.py`: Decomposed `create_pydantic_ai_provider` into table-driven provider factories.
    - `rag/embeddings.py`: Flattened `_probe_ollama_dimension` and `embed_texts`.
    - `k8s/credentials.py`: Flattened `fetch_grafana_password` via `itertools.product` and dedicated field locator.
    - `security/aibom.py`: Flattened `extract_aibom_components` via dedicated parameter parsers.
    - `security/complexity.py`: Flattened `run_complexity_scan` via `_evaluate_function_findings`.
    - `security/vault_broker.py`: Flattened `get_secret` via `_fetch_vault_kv2_secret`.
    - `ai/harness/filesystem.py`: Extracted 8 helper methods from `get_tools()` on `FileSystem`, reducing complexity from 49 to $\le 6$.
    - `ai/ast_stream.py`: Flattened `stream_ast_symbols` and `stream_token_lines` by extracting AST and token classification helpers.
    - `ai/response_repair.py`: Flattened `_extract_tool_invocations_from_chunk`.
    - `output/formatters/scalars.py`: Flattened `format_repo_map_text`.
    - `ai/analyze/scanner.py`: Flattened `_extract_file_dependencies`.
    - `ai/agents/runner.py`: Flattened `_execute_single_tool`.
- **Test Collection & Warning Hygiene**:
  - Set `__test__ = False` on `TestModel` in `src/devops_cli/ai/agents/testing.py` to eliminate `PytestCollectionWarning`.
  - Safely closed unawaited coroutine objects during synchronous toolset introspection in `toolsets/__init__.py` and `agents/agent.py` to eliminate `RuntimeWarning`.
- **Quality Gate**:
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (test, coverage $\ge 90\%$, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-06] Replace Redis with Valkey Across Workstation Infrastructure & LLM Stack
- **ArgoCD In-Memory Cache Migration**:
  - `k8s/argocd/values.yaml`: Overrode default Redis container image with `valkey/valkey:8.0-alpine` under the BSD-3-Clause open-source license.
  - Rolled out the upgrade on the live minikube cluster (`helm upgrade argocd argo/argo-cd`), validating the rollout of `deployment/argocd-redis` and verifying responsive `valkey-cli ping` -> `PONG`.
- **LLM Stack & OpenWebUI Coordination**:
  - `k8s/llm/values-open-webui.yaml`: Documented python-socketio driver configuration connecting to standalone Valkey (`valkey.llm.svc.cluster.local:6379/0`) and kept embedded Redis subchart disabled.
  - Confirmed active cluster Valkey deployment (`deployment/valkey`) is healthy and responsive in the `llm` namespace.
- **Test-First Verification & Hygiene**:
  - Authored `tests/test_k8s_valkey_stack.py` verifying stack values, image overrides, and the absence of unmaintained/proprietary Redis images across `k8s/`.
  - Updated mock data and prompt fixtures in `tests/test_output.py` and `tests/test_pydantic_ai_format_prompt.py` to reference Valkey.
  - Updated `k8s/README.md` and `docs/DEVCONTAINER_USAGE.md`.

### [2026-09-06] Address Review Findings (Session 20260905-202119) & Self-Improvement Loop Hardening
- **Codebase Security & Hardening Remediations (18 Findings Across 16 Modules)**:
  - `src/devops_cli/ai/ast_stream.py`: Added explicit symlink check (`p.is_symlink()`) in `stream_python_symbols` to prevent following untrusted symbolic links during AST parsing.
  - `src/devops_cli/ai/diff/difftastic.py`: Validated git `branch` and `base` ref arguments against command-injection metacharacters (`_GIT_REF_RE`), masked raw stderr on subprocess failure, and integrated secret sanitization.
  - `src/devops_cli/ai/prompt_eval.py`: Validated `dataset_path` against symbolic links and path traversal outside the repository or workspace root.
  - `src/devops_cli/crypto/ssh_keys.py`: Checked that target key file paths (`private_key_path`, `public_key_path`) are not existing symlinks prior to writing.
  - `src/devops_cli/ai/providers/ollama.py`: Validated `base_url` using `validate_service_url` to prevent SSRF against unauthorized destinations.
  - `src/devops_cli/ai/harness/os_access.py`: Blocked dangerous `os`, `sys`, `subprocess`, `shutil`, `socket` modules and dynamic execution builtins in safe code mode.
  - `src/devops_cli/core/process.py`: Masked sensitive credentials in `subprocess.error_sample` recorded to telemetry spans on subprocess failures.
  - `src/devops_cli/ai/agents/memory.py`: Sanitized sensitive tokens and secrets before auto-summarizing conversation memory.
  - `src/devops_cli/core/cli.py`: Masked sensitive credentials in `cli.error` telemetry span attributes on subcommand failures.
  - `src/devops_cli/ai/agents/runner.py`: Masked credentials in tool validation and runtime exception messages.
  - `src/devops_cli/docker/sandbox.py`: Added `_validate_workspace_dir` to reject symbolic link mounts and forbid mounting sensitive host root filesystems (`/`, `/etc`, `/usr`, `/var`, `/dev`, etc.).
  - `src/devops_cli/security/dive.py`: Checked that dive executable in `PATH` is not a symbolic link.
  - `src/devops_cli/ai/providers/__init__.py`: Validated `base_url` using `validate_service_url` in `create_pydantic_ai_provider`.
  - `src/devops_cli/k8s/diff.py`: Masked secrets in Helm diff output.
  - `src/devops_cli/security/complexity.py`: Skipped symbolic links in `run_complexity_scan`.
  - `src/devops_cli/security/tflint.py`: Skipped symbolic links in `_run_native_fallback_tf_lint`.
  - `src/devops_cli/commands/pipeline.py`: Sanitized pipeline path error messages to prevent full host path disclosure.
  - `src/devops_cli/server/routes/status.py`: Masked sensitive user home directory paths (`/home/...`, `/Users/...`) in workstation status endpoint.
- **Review Session & Hallucination System Hardening**:
  - Invalidate false-positive findings claiming `DEFAULT_HTTP_BROKER` does not exist (symbol was and is defined in `devops_cli.config.constants`).
  - Registered `DEFAULT_HTTP_BROKER` missing export claim in `common_hallucinations.json` and invalidated session finding 20260905-202119-001.
  - Renamed test files to domain-specific names (`test_network_security_and_trace_correlation.py`, `test_runtime_security_and_ssrf_hardening.py`).
- **Prompts, Personas, and Verification Hardening**:
  - `src/devops_cli/ai/personas/devsecops/prompt.md`: Mandated ground-truth verification in source modules before asserting missing imports or undefined symbols.
  - `src/devops_cli/ai/tasks/verify_finding_system.md`: Added rule to immediately invalidate findings claiming missing symbols without AST confirmation.
  - `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`: Documented ground-truth symbol verification in review task manual.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_security_remediation_and_hardening.py` (19/19 tests passing).
  - All 10 CI quality gates verified green via `uv run devops ci` (coverage 90.08%, strict mypy, ruff format/lint, security audit, docs sync).

### [2026-09-05] Codebase Hygiene, Elimination of Forbidden Patterns, and Zombie Code Removal
- **Elimination of Incomplete Literal Collections of File Extensions**:
  - `src/devops_cli/ai/rag/chunker.py`: Removed hardcoded extension sets (`_DOC_EXTENSIONS`, `_IAC_EXTENSIONS`, `_CONFIG_EXTENSIONS`, `_JS_TS_EXTENSIONS`, `_C_LIKE_EXTENSIONS`). Refactored category resolution and language dispatch to dynamic `mimetypes` and `detect_language` inspection.
  - `src/devops_cli/ai/rag/indexer.py`: Removed 63-element hardcoded `_INDEXABLE_EXTENSIONS` set. Implemented dynamic POSIX null-byte text detection (`is_text_file`).
  - `src/devops_cli/security/reference_extractor.py`: Removed 62-element `_COMMON_FILE_EXTENSIONS` and 9-element `_PACKAGE_ARCHIVE_EXTENSIONS`. Registered archive formats dynamically in `mimetypes` and refactored `is_file_reference` and `is_package_repository_asset` to leverage `mimetypes`, `detect_language`, Public Suffix List (`tldextract`), and filesystem queries.
- **Monkey-Patch Shim Elimination & Native `RunContext` Subclass**:
  - `src/devops_cli/ai/agents/context.py`: Removed monkey-patching shims (`_run_context_init_shim`, `_run_context_model_copy`) on `NativeRunContext`. Implemented clean, native `class RunContext[DepsT](NativeRunContext[DepsT])` with complete type annotations.
- **Unnecessary Aliases & Zombie Code Removal**:
  - `src/devops_cli/ai/tools/__init__.py`: Removed legacy `.func` alias on `Tool` in favor of canonical `.function`.
  - `src/devops_cli/ai/mcp/toolset.py`: Removed duplicate `NativeMCPToolset = MCPToolset` alias.
  - `src/devops_cli/exceptions/base.py`: Removed legacy `.code` alias on `DevOpsCLIError` in favor of canonical `.error_code`.
  - `src/devops_cli/commands/scan.py`: Removed command aliases `scan gitleaks`, `scan semgrep`, `scan checkov` and module aliases `main`, `scan_main`, `scan_app` in favor of canonical subcommands (`secrets`, `sast`, `iac`).
  - `src/devops_cli/commands/rag.py`: Removed `reset` command alias in favor of canonical `clear`.
  - `src/devops_cli/ai/harness/shell.py`: Removed duplicate `run_shell` alias tool from `Shell.get_tools()`.
- **Parameter & Fallback Consolidation**:
  - `src/devops_cli/ai/harness/compaction.py`: Consolidated `record_usage` into `record_request`, eliminating duplicate `current_time` in favor of unified `now`.
  - `src/devops_cli/config/settings.py` & `runner.py`: Removed legacy fallback `DEVOPS_DATA_DIR` in favor of canonical `DEVOPS_CLI_DATA_DIR`.
- **Mathematical Similarity Over Synthetic Scoring**:
  - `src/devops_cli/ai/review/common_hallucinations.py`: Replaced arbitrary synthetic scoring floats (`0.85`, `0.15`, `0.35`) in `calculate_hallucination_similarity` with mathematical set keyword overlap ratios and structural signature matching.
- **Comprehensive Quality Gates**:
  - Authored test-first specification suite `tests/test_codebase_hygiene_and_shims.py` (14/14 green).
  - Synchronized documentation via `devops docs generate --sync-readme`.
  - Strict type checking (`mypy --strict`) 100% clean across 306 source files.

### [2026-09-05] Code Review Findings Remediation (Session 141532) & Review Loop Hardening
- **Autonomous Hallucination Catalog & Matching Engine Hardening (`src/devops_cli/ai/review/common_hallucinations.py`, `.data/common_hallucinations.json`)**:
  - Expanded `_FORBIDDEN_COMMON_WORDS` with comprehensive English stop words, grammatical markers, and engineering vocabulary to prevent generic words from entering hallucination signature keywords.
  - Implemented category-aligned similarity guards (`syntax_grammar` never matches security findings like path traversal, SSRF, or command injection).
  - Enforced minimum compound keyword threshold (at least 2 distinct keywords) when no signature regex matches.
  - Protected canonical builtin definitions against unintended resolution overwrites in auto-recording.
  - Reset `.data/common_hallucinations.json` back to canonical definitions.
- **Secret Sanitizer Regex Protection (`src/devops_cli/ai/review/sanitization.py`)**:
  - Updated secret detection regex to require assignment/token context (`(?:[:=]\s*["']?|\bBearer\s+|\btoken\s+|["'])`), preventing variable identifiers (e.g. `secret_storage_failed`, `secret_rotation_interval`) from being masked in code diffs.
- **Codebase Security & Robustness Remediations**:
  - `src/devops_cli/ai/ext_langchain.py`: Added `urllib.parse.unquote` decoding before path traversal checks and decomposed nested argument validation into pure module-level `_validate_langchain_kwargs`.
  - `src/devops_cli/ai/agents/media.py`: Added SHA-256 64-character hex regex validation and directory containment checks on `media_id` in `DiskMediaStore.get()` and `delete()`.
  - `src/devops_cli/security/vault_broker.py`: Added percent-decoding `unquote` in `parse_vault_uri()` before path containment checks to prevent URL-encoded directory traversal.
  - `src/devops_cli/ai/review/auto_fix.py`: Added strict repository containment verification before writing to candidate remediation branches.
  - `src/devops_cli/ai/common_tools.py` & `src/devops_cli/ai/agents/capabilities.py`: Reordered validation in `web_fetch_tool` so `blocked_domains` is evaluated before allowlists and SSRF DNS resolution. Added case-insensitive domain matching and strict redirect SSRF validation. Forwarded `blocked_domains` from `WebFetch` capability to `web_fetch_tool`.
  - `src/devops_cli/k8s/chaos_runner.py`: Validated `namespace` and `victim` against CLI flag injection (`-` prefix) and inserted `--` before the pod victim argument in `kubectl delete pod`.
  - `src/devops_cli/ai/diff/difftastic.py`: Validated git `branch` and `base` ref arguments against leading hyphens.
  - `src/devops_cli/security/complexity.py` & `src/devops_cli/security/kubelinter.py`: Relativized output file paths against the repository root to prevent absolute system path disclosure.
- **Persona & System Prompt Enhancements**:
  - `src/devops_cli/ai/personas/devsecops/prompt.md`: Added Python 3.14+ PEP 758 bracketless exception awareness and sanitization placeholder guidance.
  - `src/devops_cli/ai/personas/architect/prompt.md`: Added modern Python runtime standards (PEP 758, union syntax).
  - `src/devops_cli/ai/tasks/verify_finding_system.md`: Added explicit invalidation criteria for variable identifiers (e.g. `secret_storage_failed`) and mandated cross-category integrity.
- **Knowledge Base & Documentation**:
  - `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`: Documented category-aligned hallucination filtering, stop words, and ground-truth verification.
  - Introspected CLI and synchronized documentation via `devops docs generate --sync-readme`.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suites: `tests/test_common_hallucinations_hardening.py` (5/5 passing) and `tests/test_runtime_security_and_ssrf_hardening.py` (11/11 passing).
  - Strict static typing (`mypy --strict`) 100% clean across all 305 source files (0 errors).
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Relocation of Agent Task Tracking Under `docs/agent/`
- **Dedicated Agent Operational Documentation & Task Tracking (`docs/agent/`)**:
  - Relocated continuous, real-time agent task tracking from workspace root (`task.md`) to dedicated tier `docs/agent/task.md` using `git mv` to preserve commit history.
  - Created `docs/agent/README.md` documenting directory structure, purpose, and operational conventions for AI coding assistants.
  - Updated `AGENTS.md` and `docs/ROUTINE_TASKS.md` to establish `docs/agent/task.md` as the canonical location for continuous task status tracking (Pending, In Progress, Completed).
  - Synchronized documentation via `devops docs generate --sync-readme`.

### [2026-09-05] Native Pydantic AI Toolsets (`pydantic_ai.toolsets`) Integration
- **Native Toolsets Subsystem (`src/devops_cli/ai/toolsets/__init__.py`)**:
  - Full native adoption of `pydantic_ai.toolsets` API specifications:
    - Re-exports core native primitives, types, and combinators: `AbstractToolset`, `AgentDepsT`, `AgentToolset`, `ApprovalRequiredToolset`, `CombinedToolset`, `DeferredLoadingToolset`, `DynamicToolset`, `ExternalToolset`, `FilteredToolset`, `FunctionToolset`, `IncludeReturnSchemasToolset`, `PrefixedToolset`, `PreparedToolset`, `RenamedToolset`, `SetMetadataToolset`, `ToolsetFunc`, `ToolsetTool`, `WrapperToolset`.
    - Modernized `AbstractToolset` bridging native asynchronous Pydantic AI execution (`await ts.get_tools(ctx) -> dict[str, ToolsetTool]`) with workstation synchronous tool inspection (`ts.get_tools() -> list[Tool]`) and prompt instructions (`ts.get_instructions()`).
    - Modernized `FunctionToolset` subclassing native `NativeFunctionToolset` with dual sync/async contracts, `add_tool()`, `add_function()`, and `@ts.tool` / `@ts.tool_plain` decorators supporting argument validators and custom metadata.
    - Implemented high-level domain toolset utilities and factories:
      - `create_function_toolset(...) -> FunctionToolset`: Factory for building function toolsets from sequences of tools or callables.
      - `combine_toolsets(*toolsets) -> CombinedToolset`: Helper combining multiple toolsets.
      - `prefix_toolset(toolset, prefix) -> PrefixedToolset`: Helper prefixing tool names with automatic underscore normalization.
      - `filter_toolset(toolset, filter_func) -> FilteredToolset`: Helper filtering tool visibility.
      - `rename_toolset(toolset, name_map) -> RenamedToolset`: Helper renaming tools within a toolset.
      - `require_approval_toolset(toolset, approval_func=None) -> ApprovalRequiredToolset`: Helper requiring approvals.
      - `defer_loading_toolset(toolset) -> DeferredLoadingToolset`: Helper deferring tool loading until unlocked.
      - `is_toolset(val) -> bool`: Fast predicate checking whether a value is an instance of native or modernized `AbstractToolset`.
      - `extract_tools_from_toolset(toolset, ctx=None) -> list[Tool]`: Robust extractor extracting `Tool` instances from any toolset synchronously or via inspection.
- **Elimination of Legacy Code & Remnants (Zero Zombie Code)**:
  - Eliminated duplicate hand-rolled implementations of `AbstractToolset` and `FunctionToolset` (136+ lines) in `src/devops_cli/ai/agents/tools.py` in favor of importing from `devops_cli.ai.toolsets`.
  - Modernized `MCPToolset` in `src/devops_cli/ai/agents/tools.py` to inherit from modernized `AbstractToolset`.
  - Updated `BaseCapability.get_toolset()` in `src/devops_cli/ai/agents/capabilities.py` to return native `FunctionToolset` via `create_function_toolset(tools=tools)`.
  - Modernized `PydanticAgent` in `src/devops_cli/ai/agents/agent.py` using `extract_tools_from_toolset` for seamless tool registration in `__init__`, `fork()`, and `_build_system_prompt_with_tools`.
  - Updated `src/devops_cli/ai/ext_langchain.py` to work cleanly with native `FunctionToolset`.
- **Package Re-exports (`devops_cli.ai.toolsets`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all native toolset types, schemas, and helper functions across public package tiers with strict typing (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_toolsets.py` (14/14 tests passing).
  - Regression verified full test suite (1,756 tests passing), including `tests/test_pydantic_agent.py`, `tests/test_ai_agent_capabilities.py`, `tests/test_pydantic_ai_tools.py`, `tests/test_ext_langchain.py`, and `tests/test_harness.py`.
  - Strict static typing (`mypy --strict`) 100% clean across all 305 source files (0 errors).
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Tools (`pydantic_ai.tools`) Integration
- **Native Tools Subsystem (`src/devops_cli/ai/tools/__init__.py`)**:
  - Full native adoption of `pydantic_ai.tools` API specifications:
    - Re-exports core native primitives, types, and schemas: `Tool`, `ToolDefinition`, `DocstringFormat`, `ToolPrepareFunc`, `ToolsPrepareFunc`, `ToolSelector`, `ToolSelectorFunc`, `matches_tool_selector`, `AgentNativeTool`, `NativeToolFunc`, `ObjectJsonSchema`, `DeferredToolRequests`, `DeferredToolResults`, `ToolApproved`, `ToolDenied`, `ArgsValidatorFunc`, `ToolFuncContext`, `ToolFuncPlain`, `ToolFuncEither`, `ToolParams`.
    - Modernized `Tool` subclassing native `pydantic_ai.tools.Tool`:
      - Backward-compatible `func` property alias and `parameters` dictionary inspection.
      - Direct callable invocation via `__call__` and `execute(ctx=None, **kwargs)`.
      - Safe argument filtering and traversal validation via `validate_args()`.
      - Function signature serialization via `to_function_signature()`.
      - Constructors `Tool.from_function` and `Tool.from_schema` supporting explicit schemas and custom validators.
    - Subclassed `DeferredToolRequests` with enhanced `build_results(approve_all=..., deny_all=...)` for streamlined human-in-the-loop approvals.
    - Implemented high-level domain tool utilities and factories:
      - `create_tool(...) -> Tool`: Flexible factory for wrapping callables into native `Tool` instances.
      - `create_tool_definition(name, description="", parameters_json_schema=None, ...) -> ToolDefinition`: Builder for native tool schemas.
      - `is_native_tool(val) -> bool`: Fast predicate checking whether a value is an instance of native `Tool`.
      - `approve_all_requests(requests) -> DeferredToolResults` and `deny_all_requests(requests, reason=...) -> DeferredToolResults`.
      - `matches_tool_selector_sync(selector, ctx, tool_def) -> bool`: Synchronous evaluation helper for tool selectors.
- **Elimination of Legacy Code & Remnants (Zero Zombie Code)**:
  - Eliminated duplicate hand-rolled implementations of `ToolApproved`, `ToolDenied`, `DeferredToolRequests`, `DeferredToolResults` in `src/devops_cli/ai/agents/capabilities.py` in favor of native `pydantic_ai.tools` classes.
  - Eliminated duplicate 170+ line `class Tool(AgentTool)` in `src/devops_cli/ai/agents/tools.py` in favor of importing native `Tool` from `devops_cli.ai.tools`.
  - Upgraded `src/devops_cli/ai/agents/context.py` to use native `pydantic_ai.tools.RunContext` with backward-compatible session and approval fields.
  - Modernized `PydanticAgent` (`agent.py`), `runner.py`, and `pipeline.py` to accept and dispatch `AgentTool | Tool` seamlessly.
- **Package Re-exports (`devops_cli.ai.tools`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all native tool types, schemas, and helper functions across public package tiers with strict typing (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_tools.py` (11/11 tests passing).
  - Regression verified full test suite (1,742 tests passing), including `tests/test_pydantic_agent.py`, `tests/test_ai_agent_deferred_tools.py`, `tests/test_harness.py`, and `tests/test_ai_agent_capabilities.py`.
  - Strict static typing (`mypy --strict`) 100% clean across all 14 modified source files.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Template (`pydantic_ai.template`) Integration
- **Native Template Subsystem (`src/devops_cli/ai/template/__init__.py`)**:
  - Full native adoption of `pydantic_ai.template` API specifications:
    - Installed official runtime dependency `pydantic-handlebars==0.2.1` in `pyproject.toml` and `uv.lock`.
    - Re-exports core native `TemplateStr` (Handlebars compiled template string supporting `RunContext.deps`, Pydantic models, dataclasses, or untyped dictionaries).
    - Implemented high-level domain template utilities and factories:
      - `create_template_str(source, deps_type=None, deps_schema=None) -> TemplateStr[Any]`: Typed factory for compiling native `TemplateStr` instances.
      - `render_template(template, deps=None) -> str`: Multi-modal template renderer executing native `TemplateStr`, string templates, or Pydantic models with graceful dictionary or attribute resolution.
      - `is_template_str(val) -> bool`: Fast predicate checking whether a value is an instance of `TemplateStr` or contains Handlebars expressions (`{{...}}`).
- **Elimination of Legacy Code & Remnants (Zero Zombie Code)**:
  - Ruthlessly removed legacy hand-rolled regex string subclass `class TemplateStr(str)` from `src/devops_cli/ai/agents/tools.py`.
  - Migrated `src/devops_cli/ai/agents/agent.py` to import native `TemplateStr` from `devops_cli.ai.template`.
- **Package Re-exports (`devops_cli.ai.template`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all template classes and helper functions across public package tiers with strict typing (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_template.py` (9/9 tests passing).
  - Regression verified `tests/test_pydantic_agent.py` (33/33 tests passing, 42/42 total).
  - Strict static typing (`mypy --strict`) 100% clean across all new and modified modules.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green.

### [2026-09-05] Native Pydantic AI Settings (`pydantic_ai.settings`) Integration
- **Native Settings Subsystem (`src/devops_cli/ai/settings/__init__.py`)**:
  - Full native adoption of `pydantic_ai.settings` API specifications:
    - Re-exports core native classes and schemas: `ModelSettings`, `ServiceTier`, `ThinkingEffort`, `ThinkingLevel`, `Timeout`, `ToolChoice`, `ToolChoiceScalar`, `ToolOrOutput`, `merge_model_settings`, and `AgentModelSettings`.
    - Implemented high-level domain settings utilities and factories:
      - `create_model_settings(...) -> ModelSettings`: Strongly-typed builder for constructing `ModelSettings` omitting None values while supporting all native cross-provider fields (`thinking`, `service_tier`, `tool_choice`, `parallel_tool_calls`, `stop_sequences`, `extra_headers`, `extra_body`).
      - `create_tool_or_output(*tools) -> ToolOrOutput`: Factory restricting function tools while permitting output tools, text, or image completion.
      - `normalize_thinking_level(thinking) -> ThinkingLevel | None`: Normalizes booleans and string levels (`minimal`, `low`, `medium`, `high`, `xhigh`).
      - `normalize_service_tier(tier) -> ServiceTier | None`: Validates and canonicalizes service tier strings (`auto`, `default`, `flex`, `priority`).
      - `normalize_tool_choice(choice) -> ToolChoice | None`: Normalizes scalar tool choices (`auto`, `none`, `required`), lists of tool names, or `ToolOrOutput`.
      - `resolve_runtime_model_settings(base, overrides, **kwargs) -> ModelSettings`: Multi-tier settings resolver combining base, override, and dynamic kwargs.
- **Subsystem Modernizations**:
  - `src/devops_cli/ai/models/ollama.py`: Integrated `create_model_settings` and `merge_model_settings` for clean model settings compilation.
  - `src/devops_cli/ai/direct.py`: Updated `ModelSettings` import to reference `devops_cli.ai.settings`.
  - `src/devops_cli/ai/agents/runner.py`: Enhanced `_resolve_thinking_preference` to check both native `thinking` (`ThinkingLevel`) and `enable_thinking`.
- **Package Re-exports (`devops_cli.ai.settings`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all settings classes, types, and factories across public package tiers with strict typing (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_settings.py` (9/9 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all new and modified modules.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green in 131s (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Run (`pydantic_ai.run`) Integration
- **Native Run Subsystem (`src/devops_cli/ai/run/__init__.py`)**:
  - Full native adoption of `pydantic_ai.run` API specifications:
    - Re-exports core native classes and schemas: `AgentRun`, `AgentRunResult`, `AgentRunResultEvent`, `BaseNode`, `End`, `EndMarker`, `ErrorMarker`, `EnqueueContent`, `GraphRun`, `GraphRunContext`, `GraphTaskRequest`, `JoinItem`, `NodeStep`, `PendingMessage`, `PendingMessagePriority`, and `current_otel_traceparent`.
    - Implemented high-level domain run utilities and factories:
      - `create_pending_message(content, priority="when_idle") -> PendingMessage`: Unified factory assembling native `PendingMessage` instances using `PendingMessage.from_content` with robust fallback to `ModelRequest` with `UserPromptPart` or existing message sequences.
      - `get_active_traceparent() -> str | None`: Resolves active W3C OpenTelemetry traceparent string, prioritizing native `current_otel_traceparent()` from `pydantic_ai._instrumentation` and falling back to OpenTelemetry span context `00-<trace_id>-<span_id>-<flags>`.
      - `format_run_summary(result) -> dict[str, Any]`: Formats structured run telemetry summaries (extracting `run_id`, `conversation_id`, ISO timestamp, stringified output, token usage breakdown, and W3C traceparent).
- **Package Re-exports (`devops_cli.ai.run`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all run classes, graph components, enqueue types, and traceparent resolution utilities across public package tiers with strict typing (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_run.py` (6/6 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all new and modified modules.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green in 143s (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Retries (`pydantic_ai.retries`) Integration
- **Native Retries Subsystem (`src/devops_cli/ai/retries/__init__.py`)**:
  - Full native adoption of `pydantic_ai.retries` API specifications:
    - Re-exports core native classes and types: `HTTPX2TenacityTransport`, `AsyncHTTPX2TenacityTransport`, `TenacityTransport`, `AsyncTenacityTransport`, `RetryConfig`, `wait_retry_after`, and `AgentRetries`.
    - Implemented high-level domain retry utilities and factories:
      - `DEFAULT_RETRYABLE_STATUS_CODES`: Standard transient error code tuple `(408, 429, 500, 502, 503, 504)`.
      - `is_retryable_status_code(status_code, retry_statuses)`: Pure predicate helper identifying transient HTTP error codes.
      - `create_retry_config(max_attempts, min_wait, max_wait, retry_statuses, reraise, **kwargs) -> RetryConfig`: Constructs production-ready tenacity retry configuration with `stop_after_attempt`, `wait_retry_after` (with exponential fallback), and exception filtering on `httpx2.TransportError`, `TimeoutException`, and retryable `HTTPStatusError`.
      - `create_retry_transport(...) -> HTTPX2TenacityTransport`: Factory constructing a synchronous HTTPX2TenacityTransport with automatic response validation and Retry-After header parsing.
      - `create_async_retry_transport(...) -> AsyncHTTPX2TenacityTransport`: Factory constructing an asynchronous AsyncHTTPX2TenacityTransport with automatic response validation and Retry-After header parsing.
      - `normalize_agent_retries(retries) -> AgentRetries`: Normalizes integer budgets, dictionaries, and Pydantic `AgentRetries` models into canonical Pydantic AI `AgentRetries` TypedDicts (`tools` and `output`).
- **HTTP Client Modernization (`src/devops_cli/ai/client/unified.py`)**:
  - `UnifiedLLMClient`:
    - Added `_create_retry_transport()` and `_create_http_client()` methods equipping HTTP clients with native `HTTPX2TenacityTransport` whenever `max_retries > 0`.
- **Package Re-exports (`devops_cli.ai.retries`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all retry classes, transports, and factories across public package tiers with strict type annotations (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_retries.py` (10/10 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all new and modified modules.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green in 113s (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Result (`pydantic_ai.result`) Integration
- **Native Result Subsystem (`src/devops_cli/ai/result/__init__.py`)**:
  - Full native adoption of `pydantic_ai.result` API specifications:
    - Re-exports core native classes and schemas: `RunUsage`, `FinalResult`, `StreamedRunResult`, `StreamedRunResultSync`, `SyncStreamBridge`, `OutputValidator`, `OutputValidatorFunc`, `OutputSchema`, `TextOutputSchema`, `AgentStream`, `AgentStreamEvent`, `best_effort_price`, `run_image_process_hooks`, and `run_output_with_hooks`.
    - Implemented high-level domain result utilities and factories:
      - `create_run_usage(input_tokens, output_tokens, requests, tool_calls, **kwargs) -> RunUsage`: Unified builder for native `RunUsage` tracking instances.
      - `calculate_usage_cost(usage, model_name, **kwargs)`: Live, dynamic cost calculation leveraging `best_effort_price`, handling `RunUsage`, `AgentUsage`, and custom usage payloads.
      - `to_final_result(output, tool_name=None, tool_call_id=None) -> FinalResult[Any]`: Constructs native `FinalResult` marker containers.
      - `to_agent_response(result) -> AgentResponse[Any]`: Universal converter transforming `AgentRunResult`, `StreamedRunResult`, `StreamedRunResultSync`, or `FinalResult` into typed `AgentResponse[T]`.
- **Agent Models Modernization (`src/devops_cli/ai/agents/models.py`)**:
  - `AgentResponse`:
    - Added `.run_usage -> RunUsage` property dynamically mapping token usage and turns to a native `pydantic_ai.usage.RunUsage` tracking instance with `opentelemetry_attributes()`.
    - Added `.to_final_result() -> FinalResult[Any]` wrapping structured or content output into a native result marker.
    - Enhanced `.from_run_result(run_res)` to dynamically extract output and usage from `AgentRunResult`, `StreamedRunResult`, `StreamedRunResultSync`, and `FinalResult`.
- **Package Re-exports (`devops_cli.ai.result`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all result classes, streaming types, and price calculation utilities across public package tiers with strict typing (`mypy --strict`) and complete `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_result.py` (9/9 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all new and modified modules.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Documentation generated and README synchronized (`devops docs generate --sync-readme`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green in 107s (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Profiles (`pydantic_ai.profiles`) & Providers (`pydantic_ai.providers`) Integration
- **Native Profiles Subsystem (`src/devops_cli/ai/profiles/__init__.py`)**:
  - Full native adoption of `pydantic_ai.profiles` API specifications:
    - Re-exports core types and constants: `ModelProfile`, `ModelProfileSpec`, `DEFAULT_PROFILE`, `DEFAULT_THINKING_TAGS`, `DEFAULT_PROMPTED_OUTPUT_TEMPLATE`, `merge_profile`, `JsonSchemaTransformer`, `InlineDefsJsonSchemaTransformer`, `StructuredOutputMode`, `ToolAdditionMode`, `ToolDeferralMode`, and `SUPPORTED_NATIVE_TOOLS`.
    - Re-exports all 14 family model profile builders: `amazon_model_profile`, `anthropic_model_profile`, `cohere_model_profile`, `deepseek_model_profile`, `google_model_profile`, `google_realtime_model_profile`, `grok_model_profile`, `grok_realtime_model_profile`, `groq_model_profile`, `harmony_model_profile`, `meta_model_profile`, `mistral_model_profile`, `moonshotai_model_profile`, `openai_model_profile`, `openai_realtime_model_profile`, `qwen_model_profile`, and `zai_model_profile`.
    - Implemented high-level domain resolution and introspection utilities:
      - `resolve_model_profile`: Resolves unified `ModelProfile` from model strings (`"openai:gpt-4o"`, `"ollama:qwen2.5-coder:7b"`, `"anthropic:claude-3-5-sonnet"`), provider hints, or `ModelProfileSpec` callables, seamlessly merging custom overrides with `merge_profile`.
      - `get_model_thinking_tags`: Introspects model-specific reasoning block delimiters (e.g. Anthropic `('<thinking>', '</thinking>')` vs default `('<think>', '</think>')`).
      - `supports_thinking`: Evaluates if a model profile natively supports chain-of-thought/reasoning output blocks.
      - `thinking_always_enabled`: Checks whether reasoning is permanent and non-suppressible (e.g. DeepSeek-R1).
      - `get_model_profile_builder`: Dynamic registry lookup mapping canonical family names to their respective profile builder functions.
- **Modernized Providers Subsystem (`src/devops_cli/ai/providers/__init__.py`)**:
  - Full native adoption of `pydantic_ai.providers` API specifications:
    - Re-exports native abstract base class `Provider`, alongside dynamic discovery utilities `infer_provider` and `infer_provider_class`.
    - Re-exports concrete native provider classes: `NativeOllamaProvider`, `NativeOpenAIProvider`, `NativeAnthropicProvider`, `NativeGoogleProvider`, `NativeDeepSeekProvider`, and `NativeOpenRouterProvider`.
    - Implemented unified factory `create_pydantic_ai_provider(provider, base_url=None, api_key=None, **kwargs)` configuring endpoint URLs, API keys, and client parameters according to provider type.
    - Preserved 100% backward compatibility for existing `BaseLLMProvider`, `get_provider(name, config)`, and legacy provider classes (`OllamaProvider`, `OpenAIProvider`, `AnthropicProvider`, `CopilotProvider`, `MockProvider`).
- **Bridge & Thinking Stream Integration (`src/devops_cli/ai/pydantic_ai_bridge.py`, `src/devops_cli/ai/thinking_stream.py`)**:
  - `resolve_pydantic_ai_model`: Configured non-ollama providers to pass user credentials and base URLs to `infer_model` via a `provider_factory` backed by `create_pydantic_ai_provider`.
  - `ThinkingStreamProcessor`, `strip_think_blocks`, and `extract_think_blocks`: Enhanced to accept dynamic `thinking_tags: tuple[str, str]` (defaulting to `DEFAULT_THINKING_TAGS`), natively supporting Anthropic's `<thinking>...</thinking>` tags and custom model delimiters.
- **Package Re-exports (`devops_cli.ai.profiles`, `devops_cli.ai.providers`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all profile and provider utilities across public package tiers with strict type annotations and comprehensive `__all__` lists.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_profiles_and_providers.py` (22/22 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all new and modified modules.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green in 133s (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Output (`pydantic_ai.output`) Integration
- **Native Output Subsystem (`src/devops_cli/ai/output/__init__.py`)**:
  - Full native adoption of `pydantic_ai.output` API specifications:
    - Re-exports core native classes and schemas: `ToolOutput`, `NativeOutput`, `PromptedOutput`, `TextOutput`, `StructuredDict`, `OutputObjectDefinition`, and `OutputContext`.
    - Re-exports types: `OutputDataT`, `OutputMode`, `StructuredOutputMode`, `OutputSpec`, `OutputTypeOrFunction`, and `TextOutputFunc`.
    - Implemented domain utilities and factories:
      - `CallableDict`: Dictionary subclass supporting both dict lookup/key inspection and callable invocation (`__call__`), enabling dual syntax compatibility between Pydantic AI's `agent.output_json_schema()` and existing property access `agent.output_json_schema["properties"]`.
      - `unwrap_output_spec`: Recursively unwraps any `OutputSpec` into underlying target Python type(s), callable(s), or dictionary definitions (handling bare BaseModels, `NativeOutput`, `ToolOutput`, `PromptedOutput`, `TextOutput`, `StructuredDict`, and sequence unions).
      - `extract_output_json_schema`: Extracts clean JSON schema dictionaries from any output marker, BaseModel, `StructuredDict`, or `TextOutput` (producing `{"type": "string"}`).
      - `resolve_output_mode`: Determines optimal output mode (`"native"`, `"tool"`, `"prompted"`, `"text"`) integrating with Ollama local vs cloud detection.
      - `build_output_spec`: High-level factory wrapping any schema in the appropriate marker based on mode.
      - Predefined review output specifications: `REVIEW_RESULT_NATIVE`, `REVIEW_RESULT_TOOL`, `REVIEW_RESULT_PROMPTED`, and dynamic factory `get_review_output_spec`.
- **Bridge & Agent Modernization (`src/devops_cli/ai/pydantic_ai_bridge.py`, `agent.py`, `response_repair.py`)**:
  - `create_pydantic_ai_agent`: Broadened to accept `OutputSpec[Any]` and optional `output_mode`, automatically wrapping schemas with `build_output_spec`.
  - `PydanticAgent`: Updated `output_type` and `output_schema` to accept `OutputSpec[Any]`, with `output_json_schema` returning `CallableDict`.
  - `fix_llm_response`: Added support for all `OutputSpec` markers, unwrapping target models, calling `TextOutput` processors on string outputs, and validating dictionary structures with `StructuredDict`.
- **Package Re-exports (`devops_cli.ai.output`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all output types, markers, and factories across all public package tiers with strict typing and comprehensive `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_output.py` (11/11 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all modified files.
  - Clean linting and formatting (`ruff check`, `ruff format`).
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

### [2026-09-05] Native Pydantic AI Ollama Model (`pydantic_ai.models.ollama`) & Provider Integration
- **Native Ollama Models Subsystem (`src/devops_cli/ai/models/ollama.py`, `src/devops_cli/ai/models/__init__.py`)**:
  - Full native adoption of `pydantic_ai.models.ollama` and `pydantic_ai.providers.ollama` API specifications:
    - Re-exports core native classes and schemas: `OllamaModel`, `OllamaProvider`, `OpenAIChatModel`, `OpenAIJsonSchemaTransformer`, `OpenAIModelProfile`, `ModelSettings`, and `ModelProfileSpec`.
    - Re-exports specialized model profile builders: `qwen_model_profile`, `deepseek_model_profile` (with native thinking extraction via `openai_chat_thinking_field: 'reasoning'`), `meta_model_profile`, `mistral_model_profile`, `google_model_profile`, `cohere_model_profile`, and `harmony_model_profile`.
    - Implemented high-level domain helpers and factories:
      - `normalize_ollama_base_url`: Robust URL normalizer ensuring a clean `/v1` endpoint path without duplication (`/v1/v1`).
      - `is_ollama_cloud`: Identifies Ollama Cloud endpoints (`ollama.com`) and cloud model suffixes (`-cloud`).
      - `get_recommended_output_mode`: Returns `"native"` (`NativeOutput`) for self-hosted Ollama (v0.5.0+ grammar-constrained schema enforcement) and `"tool"` (`ToolOutput`) for Ollama Cloud (mitigating unconstrained schema generation).
      - `create_ollama_provider`: Builds native `OllamaProvider` with cluster endpoint fallback, environment variable inspection (`OLLAMA_BASE_URL`, `OLLAMA_API_KEY`), and authentication token forwarding.
      - `create_ollama_model`: High-level factory configuring `OllamaModel` with resolved provider, domain `ModelSettings` (temperature, max_tokens, reasoning_effort, timeout), and profile overrides.
- **Bridge & Model Resolution Modernization (`src/devops_cli/ai/pydantic_ai_bridge.py`)**:
  - Refactored `resolve_pydantic_ai_model` to delegate Ollama model resolution to `create_ollama_model`, passing active settings (`temperature`, `max_tokens`, `reasoning_effort`, `ollama_urls`, `api_key`).
- **Package Re-exports (`devops_cli.ai.models.ollama`, `devops_cli.ai.models`, `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`)**:
  - Re-exported all native Ollama types, profile builders, and factories across all public package tiers with strict typing and comprehensive `__all__` definitions.
- **Quality Gates & Test-First Verification**:
  - Authored comprehensive test suite `tests/test_pydantic_ai_ollama.py` (9/9 tests passing).
  - Strict static typing (`mypy --strict`) 100% clean across all modified files.
  - Full CI validation suite (`uv run devops ci`): 10/10 quality gates green (version, test, coverage >= 90%, lint, format, typecheck, audit, security, actionlint, docs).

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
