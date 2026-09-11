# Task 148: Decouple Circular Module Imports & Streamline Convoluted Import Patterns

**Issue**: [#148](https://github.com/dan-petty/devops-cli/issues/148)
**PR**: [#149](https://github.com/dan-petty/devops-cli/pull/149)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p2-medium`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Static AST import analysis of `src/devops_cli/` revealed several import cycles and convoluted import patterns:

1. **Cycle #4: `devops_cli.ai.review` Subsystem (3 modules)**:
   - `devops_cli.ai.review.runner` imported `ReviewPipelineOrchestrator` from `devops_cli.ai.review.pipeline`.
   - `devops_cli.ai.review.pipeline` imported `_read_candidate_conventions_file` from `devops_cli.ai.review.runner` (deferred in-function).
   - `devops_cli.ai.review.stages.reporting` imported `_get_reviews_base_dir` from `devops_cli.ai.review.pipeline`, while `pipeline` imported `stages.reporting`.
   - **Remediation**: Extracted shared convention reading (`_read_candidate_conventions_file`) and filesystem path resolvers (`_get_reviews_base_dir`) into a dedicated leaf utility module (`devops_cli.ai.review.review_environment`) so that `runner`, `pipeline`, and `stages.reporting` only import downward.

2. **Cycle #3: `devops_cli.commands.k8s` Parent-Child Cycle (8 modules)**:
   - `devops_cli.commands.k8s.__init__` imported all subcommand modules (`cluster_context`, `networking`, `bootstrap`, `stack_lifecycle`, `cluster_runtime`, `security_audit`, `tls_management`).
   - Submodules (e.g. `tls_management.py`) imported the parent package `devops_cli.commands.k8s`.
   - **Remediation**: Submodules now import directly from siblings (`cluster_runtime`, `networking`, `stack_lifecycle`) without parent package re-entry. In `k8s.__init__.py`, `_K8sModule` forwards mock patch operations down to runtime submodules so test mocks continue to function transparently with zero circular imports.

3. **Cycle #1: `devops_cli.output` Subsystem (7 modules)**:
   - `devops_cli.output.models` imported `devops_cli.output.formatter` (in-function).
   - `devops_cli.output.formatters.tables` imported `scalars.py`, and `scalars.py` imported `tables.py`.
   - `devops_cli.output.formatters.panels` imported `console.py`, `tables.py`, and `scalars.py`.
   - `devops_cli.output.console` imported `formatter.py` and `models.py`.
   - **Remediation**: Decoupled formatters by extracting `markup.py` and `dispatcher.py`. Implemented native Rich `Table` rendering in `TablePayload.render()`, decomposed into clean helpers to maintain nesting $\le 2$. Removed 24 in-function deferred imports in `tables.py` and `panels.py`.

4. **Convoluted Deferred In-Function Imports**:
   - Replaced fragile in-function import workarounds with clean, architectural module hierarchies.
   - Decoupled `ai.text_utils` from `review_schema.py` to prevent cyclic re-entry in `thinking_stream.py` and `response_repair.py`.

---

## 2. Implementation Summary

1. **AI Review Subsystem**:
   - Added [src/devops_cli/ai/review/review_environment.py](file:///workspaces/devops-cli/src/devops_cli/ai/review/review_environment.py).
   - Refactored `pipeline.py`, `runner.py`, `stages/reporting.py`, `exporter.py`, and `patching.py` to use `review_environment`.
2. **Output Subsystem**:
   - Added [src/devops_cli/output/markup.py](file:///workspaces/devops-cli/src/devops_cli/output/markup.py) and [src/devops_cli/output/formatters/dispatcher.py](file:///workspaces/devops-cli/src/devops_cli/output/formatters/dispatcher.py).
   - Refactored `models.py`, `console.py`, `formatters/tables.py`, and `formatters/panels.py`.
3. **Kubernetes Commands Subsystem**:
   - Implemented `_K8sModule` attribute forwarding in `k8s/__init__.py`.
   - Refactored `bootstrap.py`, `cluster_context.py`, `networking.py`, `security_audit.py`, `stack_lifecycle.py`, and `tls_management.py` to reference sibling modules directly.
4. **Architectural Invariant Enforcement**:
   - Added `test_no_circular_imports_in_decoupled_subsystems` to [tests/test_architectural_invariants.py](file:///workspaces/devops-cli/tests/test_architectural_invariants.py) enforcing zero cycles via Tarjan's Strongly Connected Components algorithm.

---

## 3. Verification

- `uv run pytest tests/test_architectural_invariants.py`: 7 passed (including cycle prevention and nesting depth $\le 5$).
- `uv run pytest tests/test_k8s.py tests/test_output.py tests/test_review.py tests/test_review_runner.py`: 79 passed.
- `uv run ruff check src tests`: Clean (0 errors).
- `uv run ruff format --check src tests`: Clean (0 errors).
- `uv run mypy src/devops_cli/ai src/devops_cli/commands/k8s src/devops_cli/output src/devops_cli/config/env.py`: Clean (0 errors).
- `devops ci`: All 10 gates passed (python_version, test, coverage 90.07%, lint, format, typecheck, audit, security, actionlint, docs).
