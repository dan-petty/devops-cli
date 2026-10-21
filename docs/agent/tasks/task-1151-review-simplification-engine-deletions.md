# Task: The persona review stage, legacy segment engine and review-time RAG are deleted, and devops review builds a model client only for the explanation stages (#1151)

**Issue**: [#1151](https://github.com/dan-petty/devops-cli/issues/1151)
**Scope**: scope/review
**Feasibility**: Verified that group analysis executes independently of the persona stage by removing the `has_personas` gate in `_run_group_analysis_stage`. Verified that `ReviewStageFlags.needs_model()` controls whether an LLM client is constructed across `devops review path`, `branch`, and `pr`. Offline tests with fake clients confirm `--no-group-analysis` makes zero calls and writes no `analysis.json`, and routed-file reviews with admitted scanner findings trigger group analysis.

## Description

Refactors the review pipeline to prepare for deleting the persona review stage and legacy segment engine:
1. Decouples finding-group model analysis from the persona review stage so it can run when personas are absent or disabled.
2. Introduces the `--no-group-analysis` CLI flag across review commands.
3. Fixes `ReviewStageFlags.to_dict()` serialization to include `group_analysis`.
4. Introduces `ReviewStageFlags.needs_model()` and ensures `devops review` constructs LLM clients only when a model-driven stage is enabled.

Delivered across 5 incremental pull requests.

## Deliverables

### PR 1: Group Analysis Without Personas (Part of #1151)

- [x] Remove `has_personas` parameter and gate from `_run_group_analysis_stage` in `src/devops_cli/ai/review/pipeline.py`.
- [x] Add `--no-group-analysis` CLI option to `path`, `branch`, and `pr` subcommands in `src/devops_cli/commands/review.py`.
- [x] Add `no_group_analysis` help text to `ReviewHelp` in `src/devops_cli/lang/en/help.py`.
- [x] Fix `ReviewStageFlags.to_dict()` in `src/devops_cli/ai/review/flags.py` to include `"group_analysis"`.
- [x] Add `ReviewStageFlags.needs_model()` returning `self.persona_review or self.group_analysis`.
- [x] Remove unused and unwired `group_analysis_only` parameter from `resolve_stage_flags` in `src/devops_cli/ai/review/flags.py`.
- [x] Make `ReviewClients.analysis` optional (`ReviewLLMClient | None = None`) in `src/devops_cli/ai/review/runner.py`.
- [x] Conditionally instantiate `_make_review_clients(...)` only when `stage_flags.needs_model()` is true in `path`, `branch`, and `pr` subcommands, defaulting to `ReviewClients()`.
- [x] Remove unconditional `get_llm_client(task="review")` fallback in `ReviewPipelineOrchestrator.__init__` in `src/devops_cli/ai/review/pipeline.py`.
- [x] Fall back to `DEFAULT_PRE_ANALYSIS_WORKERS` in pre-analysis batch worker sizing when `self.llm_client` is None in `src/devops_cli/ai/review/pipeline.py`.
- [x] Regenerate CLI documentation (`docs/CLI_REFERENCE.md`, `docs/commands/*.md`, `docs/MCP_TOOLS.md`).
- [x] Add comprehensive unit and integration tests in `tests/test_review_stage_flags.py` and `tests/test_review_group_analysis.py`.

### PR 2: Deletions of Persona Review Stage, Legacy Segment Engine, and Review-Time RAG (Part of #1151)

- [x] Delete obsolete review modules and prompt templates:
  - `src/devops_cli/ai/review/classification.py`
  - `src/devops_cli/ai/review/contract_grounding.py`
  - `src/devops_cli/ai/tasks/code_review_prompt.md`
  - `src/devops_cli/ai/tasks/config_review_prompt.md`
  - `src/devops_cli/ai/tasks/docs_review_prompt.md`
  - `src/devops_cli/ai/tasks/mcp_code_review_output.md`
  - `tests/test_review_classification.py`
  - `tests/test_review_prompt_consistency.py`
  - `tests/test_review_loop_calibration.py`
- [x] Refactor `src/devops_cli/ai/review/pipeline.py` (deleting >1,000 lines):
  - Remove multi-persona review execution methods (`execute_multi_persona_review`, `_execute_single_page_review`, `_safe_review_file_payload`, `_build_page_review_prompt`, `_execute_page_review_steps`, `_execute_page_review_with_backoff`, `_read_target_conventions`, `_build_multi_persona_pipeline`, `_resolve_file_pipeline`).
  - Remove finding re-ranking stage (`execute_finding_reranking`, `_rerank_single_file_payload`).
  - Remove review-time RAG and contract grounding integration (`_resolve_rag_and_contract_context`, `ground_contracts`, `conventions_revision`).
  - Replace heuristic fuzzy deduplication (`consolidate_duplicate_findings`, `_are_findings_duplicate`, `_share_distinctive_symbol`, `_extract_code_symbols`) with exact deduplication by `(fingerprint, location)` via `_collect_and_deduplicate_findings`.
  - Update `SavedFinding` models, console tables, and markdown report generation to replace `persona` with `producer` and `fingerprint`.
  - Remove `ai_scratchpad` from `FileReviewPayload`.
- [x] Remove obsolete review flags and CLI options:
  - Remove `--persona`, `--all` (`--all-personas`), `--no-persona-review`, `--persona-review-only`, `--no-reranking`, `--reranking-only` from `src/devops_cli/commands/review.py` and `src/devops_cli/ai/review/flags.py`.
  - Enforce exiting with code 2 and deprecation guidance when removed options are passed.
- [x] Update telemetry:
  - Update `FINDINGS_TOTAL` metric to emit `producer` label rather than `persona`.
  - Update `docs/TELEMETRY.md` and Kubernetes dashboard `k8s/monitoring/dashboards/devops-cli.json`.
- [x] Ratchet down swallowed failure ceilings:
  - Update `tests/fixtures/swallowed_failures_ceilings.json` via `--lower`.
- [x] Synchronize documentation and regenerate command docs:
  - Update `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md` and `docs/DEVCONTAINER_USAGE.md`.
  - Run `uv run devops docs generate --sync-readme` and verify with `uv run devops docs check`.
- [x] Verify offline test suites:
  - Add `tests/test_review_deduplication.py` asserting exact deduplication on `(fingerprint, location)`.
  - Add `tests/commands/test_review_removed_options.py` asserting removed options exit 2.
  - Adapt existing test suites to the simplified review pipeline architecture.

### Follow-up Pull Requests

- PR 3: Diff parsing and target extraction relocations to `diff.py` and `targets.py`, deletion of `chunker.py` (Part of #1151).
- PR 4: Hand-written doc updates, `.devops/review.md` deletion, and changelog fragment (Closes #1151).
- PR 5: #1150 leftovers (hardening surface to `.devops/review.toml`, verifier note kind constants, `relocated_from`) (Part of #1151).
