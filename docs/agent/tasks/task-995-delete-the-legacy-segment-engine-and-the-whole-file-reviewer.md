# Task 995: Delete the Legacy Segment Engine and the Whole-File Reviewer

**Issue**: [#995](https://github.com/dan-petty/devops-cli/issues/995)
**Status**: Done
**Milestone**: `v0.2.34`
**Priority**: `priority/p2-medium`
**Scope**: `type/refactor`, `scope/review`, `priority/p2-medium`
**Feasibility**: Verified that `ReviewPipelineOrchestrator` in `src/devops_cli/ai/review/pipeline.py` is the active production review engine, while `_run_persona_loop` and the legacy segment engine in `src/devops_cli/ai/review/runner.py` and `verification.py` are dead branches reached only via `type(clients.analysis).__name__ == "LLMClient"` checks and legacy test harnesses.

---

## 1. Description & Objectives

Delete the legacy segment engine and whole-file reviewer in `ai/review/runner.py` and `ai/review/verification.py`, leaving `ReviewPipelineOrchestrator` as the single review engine. Remove the class-name check `type(clients.analysis).__name__ == "LLMClient"`, type LLM clients with a clean `typing.Protocol`, delete the deprecated compose task and legacy task prompts, ensure `--summary` returns before orchestrator construction, and ensure lockfile-only or empty diffs exit early without model calls or session directory creation.

#### Key Deliverables:
- [x] **Single Engine & Class-Name Check Removal** (`src/devops_cli/ai/review/runner.py`):
  - Removed `if type(clients.analysis).__name__ == "LLMClient":` branch and `_run_persona_loop`.
  - Deleted dead functions only reached by the legacy persona loop (32 functions in `runner.py` including `_resolve_ollama_urls`, `_collect_files`, `_resolve_static_analyzer_states`, and legacy formatting/saving helpers).
  - Deleted legacy verification helpers in `src/devops_cli/ai/review/verification.py` (`_merge_segment_results`, `_reconcile_verified`, `_format_segment_findings`).
- [x] **Early Summary & No-File Handling** (`src/devops_cli/ai/review/runner.py`):
  - Checked `--summary` before building `ReviewPipelineOrchestrator`, printing metadata and exiting without creating a session directory or invoking models.
  - Verified no-file / lockfile-only diffs exit with message and no model requests.
- [x] **LLM Client Protocol** (`src/devops_cli/ai/review/protocol.py`, `src/devops_cli/ai/review/pipeline.py`):
  - Defined `ReviewLLMClient` Protocol declaring `chat`, `chat_messages`, `get_context_window`, and `backend_info`.
  - Typed `ReviewPipelineOrchestrator` parameters `llm_client` and `verification_client` with the protocol.
- [x] **Deletion of Compose Task & Legacy Prompts**:
  - Deleted `ai.tasks.compose` field, `AI_TASK_COMPOSE_*` options, `DEVOPS_CLI_AI_TASK_COMPOSE_*` environment variables, `ReviewClients.compose`, `PersonaDefinition.compose_prompt`, and task prompt `ai/tasks/compose.md`.
  - Deleted legacy prompts: `paginated_review_protocol.md`, `review_output_instruction.md`, `path_review_prompt.md`.
  - Removed `sanitization._build_prompt`, `runner._build_path_prompt`, `_load_agents_md`.
- [x] **Findings JSON Consolidation**:
  - `generate_consolidated_report` is the sole creator of `findings.json` sessions.
- [x] **Consolidated #789 Invariant**:
  - Preserved UNVERIFIED high findings in reports with REQUEST CHANGES recommendations; only INVALIDATED findings are excluded from reports.
- [x] **Documentation & CI Verification**:
  - Regenerated CLI documentation and configuration docs.
  - Authored changelog fragment `changelog.d/995.md`.
  - 100% passing status across `uv run devops ci`.
