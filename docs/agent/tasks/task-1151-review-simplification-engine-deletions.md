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

### PR 5: Remove #1150 Leftovers (Part of #1151)

- [x] Replace `"common_hallucinations.json"` in `CONST_HARDENING_SURFACES` (`src/devops_cli/config/constants.py`), `match_hardening_surface` (`src/devops_cli/github/defect_classifier.py`), and `.github/workflows/defect-pr-hardening-audit.yml` with `".devops/review.toml"` and `"src/devops_cli/review/rules/"`.
- [x] Delete `CONST_VERIFICATION_NOTE_KINDS` and its ten verifier note constants (`CONST_VERIFICATION_UNAVAILABLE`, `CONST_VERIFIER_NO_VERDICT`, `CONST_VERIFIER_REPLY_UNPARSED`, `CONST_VERIFIER_REPLY_CUT`, `CONST_VERIFIER_SELF_REFUTATION`, `CONST_VERIFIER_INCONCLUSIVE`, `CONST_CRITERIA_NON_DISCRIMINATING`, `CONST_MITIGATION_UNPROVEN`, `CONST_CITATION_OUT_OF_RANGE`, `CONST_VERIFIER_CONTRADICTION`) from `src/devops_cli/config/constants.py`.
- [x] Remove `("verification_note", "Verification note")` from `CONST_FINDING_DETAIL_SECTION_FIELDS` in `src/devops_cli/config/constants.py`.
- [x] Remove `verification_note` and `relocated_from` fields from `Finding` in `src/devops_cli/ai/review_schema.py`, along with `_unverified_note_counts` and the `"verification_note"` key from `compute_verdict_distributions`, `apply_verdict` (`src/devops_cli/ai/review/verdicts.py`), and `_VERDICT_FIELDS` (`src/devops_cli/ai/review/adjudication.py`).
- [x] Rewrite `src/devops_cli/ai/personas/challenger/role.md` and `src/devops_cli/ai/personas/challenger/prompt.md` so the challenger argues against a claim, design, or plan in chat and names the evidence that would settle it.
- [x] Update unit and contract tests in `tests/test_defect_classifier.py`, `tests/test_pr_hardening_report.py`, `tests/test_review_verification.py`, `tests/test_verdict_writers.py`, `tests/test_verdict_polarity.py`, and `tests/test_ui_reactive.py`.

### PR 2: Deletions of Persona Review Stage, Legacy Segment Engine, and Review-Time RAG (Part of #1151)

- [x] Delete `_run_persona_stage` and legacy segment engine from `src/devops_cli/ai/review/pipeline.py`.
- [x] Delete review-time RAG context injection from `src/devops_cli/ai/review/pipeline.py`.
- [x] Remove `--persona` option from `path`, `branch`, and `pr` review subcommands in `src/devops_cli/commands/review.py`.
- [x] Update review stage flags, runner, and profile accounting.
- [x] Update test suites for persona deletions in `tests/test_review_pipeline.py`.

### PR 3: Diff Parsing and Target Extraction Relocations (Part of #1151)

- [x] Relocate review diff parsing to `src/devops_cli/ai/review/diff.py`.
- [x] Relocate review target path extraction and resolution to `src/devops_cli/ai/review/targets.py`.
- [x] Delete obsolete `src/devops_cli/ai/review/chunker.py`.
- [x] Update imports and callers across review engine, runner, and test suites.

### PR 4: Documentation Updates, Convention Cleanup, and Changelog (Closes #1151)

- [x] Delete repository-level `.devops/review.md` and clean up convention-dependent tests in `tests/test_personas.py`, `tests/test_agents_md_claims.py`, and `tests/test_review_project_conventions.py`.
- [x] Update documentation across `README.md`, `AGENTS.md`, `CONTEXT.md`, `docs/KNOWN_ISSUES.md`, `docs/RELEASE_NOTES.md`, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, `docs/SELF_IMPROVEMENT.md`, and docs layouts.
- [x] Update AI knowledge base manuals in `src/devops_cli/ai/knowledge_base/` (`devops_cli/` and `it_domains/`) to remove obsolete multi-persona review references.
- [x] Update command docstrings and help strings in `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/review.py`, and `src/devops_cli/ai/explain.py`.
- [x] Regenerate CLI documentation and sync README command matrix via `uv run devops docs generate --sync-readme`.
- [x] Add changelog fragment `changelog.d/1151.md` documenting deletions, changes, and additions.
