# Task: Delete Pass-Through Package Facades and StagePipeline Protocols (#1002)

**Issue**: [#1002](https://github.com/dan-petty/devops-cli/issues/1002)
**Scope**: scope/ai
**Feasibility**: Verified against repository AST import structures with `tests/test_architectural_invariants.py::test_no_non_submodule_imports_from_ai_and_github_facades`, package inits holding only docstrings, and offline test executions.

## Description

The top-level package facades `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.mcp`, and `devops_cli.github` previously re-exported hundreds of symbols and caused massive eager import chains. In addition, dead compatibility modules `pydantic_agent.py`, `ai/pipeline_protocol.py`, and the legacy `devops_cli.pipeline` package remained in the tree. This task (PR 1 of 3 for #1002) mechanically removes the package facade re-exports, leaving `__init__.py` files with only single module docstrings, deletes the dead modules and legacy pipeline engine, updates all callers across `src/`, `tests/`, and knowledge base documentation to import directly from defining submodules, and ratchets down suppression ceilings.

## Acceptance Criteria

- [x] Package `__init__.py` files for `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.mcp`, and `devops_cli.github` hold only single module docstrings.
- [x] Architectural invariant test `test_no_non_submodule_imports_from_ai_and_github_facades` enforces zero non-submodule imports from these facades across `src/`, `tests/`, and knowledge base docs.
- [x] Dead modules `src/devops_cli/ai/agents/pydantic_agent.py`, `src/devops_cli/ai/pipeline_protocol.py`, and the entire `src/devops_cli/pipeline/` package are deleted along with their obsolete test suites.
- [x] All imports in `src/` and `tests/` point directly to defining submodules.
- [x] Suppression ceilings and swallowed failures ratchets are lowered to reflect removed suppressions.
- [x] Lazy import optimization ensures `devops --version`, `devops --help`, and all `devops <group> --help` commands load zero heavy modules (`pydantic_ai`, `kubernetes`, `docker`, `fastmcp`, `qdrant_client`, `opentelemetry`).
- [x] SSRF validation helpers in `devops_cli.core.validation` and `devops_cli.http.egress` lazified to prevent running commands (`devops ci`, tracer, http client) from eagerly importing `pydantic_ai`.
- [x] Pydantic AI exception classes decoupled into `devops_cli.exceptions.ai_pydantic` and lazily re-exported in `devops_cli.exceptions.ai`.
- [x] Pass-through package facades `devops_cli.ai.rag`, `devops_cli.ai.review`, and `devops_cli.ai.benchmark` made lazy via `__getattr__`.
- [x] FastMCP server imports in `devops_cli.commands.mcp` made lazy inside command functions.
- [x] Comprehensive startup import isolation tests added in `tests/test_cli_startup_imports.py`.
- [x] `uv run devops ci` passes with 100% success.
- Follow-up PR 3 (#1002): Dry-run imports, import time budget invariants, and closing changelog fragment.

## Deliverables

- [x] Replaced `src/devops_cli/ai/__init__.py`, `src/devops_cli/ai/agents/__init__.py`, `src/devops_cli/ai/mcp/__init__.py`, and `src/devops_cli/github/__init__.py` with single module docstrings.
- [x] Deleted dead files: `src/devops_cli/ai/agents/pydantic_agent.py`, `src/devops_cli/ai/pipeline_protocol.py`, `src/devops_cli/pipeline/__init__.py`, `src/devops_cli/pipeline/models.py`, `src/devops_cli/pipeline/pipeline.py`, `src/devops_cli/pipeline/stage.py`, `tests/test_pipeline_engine.py`, and `tests/test_pipeline_protocol.py`.
- [x] Re-pointed all callers across `src/devops_cli/`, `tests/`, and `src/devops_cli/ai/knowledge_base/` directly to defining submodules.
- [x] Lowered `DEFAULT_C901_SUPPRESSION_CEILING` to 49 and `src type: ignore` ceiling to 89 in `src/devops_cli/config/defaults.py`.
- [x] Ratcheted down swallowed failures ceilings in `tests/fixtures/swallowed_failures_ceilings.json`.
- [x] Added architectural invariant test in `tests/test_architectural_invariants.py`.
- [x] Lazified SSRF helpers and constants in `src/devops_cli/core/validation.py` and `src/devops_cli/http/egress.py`.
- [x] Decoupled `pydantic_ai` exceptions to `src/devops_cli/exceptions/ai_pydantic.py` with lazy re-export in `src/devops_cli/exceptions/ai.py`.
- [x] Made `src/devops_cli/ai/rag/__init__.py`, `src/devops_cli/ai/review/__init__.py`, and `src/devops_cli/ai/benchmark/__init__.py` lazy via `__getattr__`.
- [x] Made `src/devops_cli/ai/response_repair.py` lazy for `pydantic_ai.messages`.
- [x] Made `src/devops_cli/commands/mcp.py` and `src/devops_cli/commands/review.py` imports lazy within command callbacks.
- [x] Added heavy module isolation tests across `--version`, `--help`, and all 39 command groups in `tests/test_cli_startup_imports.py`.
