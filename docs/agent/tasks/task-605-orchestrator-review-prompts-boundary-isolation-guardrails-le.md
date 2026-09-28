# Task 605: Orchestrator Review Prompts Boundary Isolation, Guardrails, Legible Empty Replies

**Issue**: [#605](https://github.com/dan-petty/devops-cli/issues/605)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

The "Multi-Persona Code Review Engine" entry marks XML prompt boundary isolation done and the matrix's "Closed-Loop Hallucination Ledger & False-Positive Rate" row marks prompt exemplars done. Both hold only on the fallback `_run_persona_loop` (`src/devops_cli/ai/review/runner.py:1969`); an `LLMClient` review with extracted files runs `ReviewPipelineOrchestrator` (`runner.py:1832,1923`). There, page content, RAG and contract context follow bare labels with no enclosing element or untrusted preamble (`src/devops_cli/ai/review/classification.py:280-285`). Persona system prompts omit `guardrails_isolation.md` and the exemplars (`src/devops_cli/ai/review/pipeline.py:1677-1680,1696`); `render_negative_exemplars` has one caller, `runner.py:222`. `persona_title` is never passed (`pipeline.py:554`), so every persona reviews as "DevSecOps Specialist" (`classification.py:246`). Guardrail tests cover only the fallback builders (`tests/test_review_prompt_guardrails.py:39-121`). An unparsed persona reply adds zero findings and the file still gets stage `reviewed` (`pipeline.py:245,1842`); only a scratchpad thought differs from a clean review. vibes isolates `<target_diff>` and `<metadata>` in XML sections, gives each persona an exclusive domain, and treats an empty findings list as legitimate output.

#### Key Deliverables:
- [x] (1) Parity, P0: build orchestrator system prompts with `_persona_system_prompt` (`runner.py:214`), wrapping conventions in `<project_conventions_context>` and appending negative exemplars and prompt isolation guardrails.
- [x] Wrap page content in `<target_code_to_review>` with untrusted material preamble.
- [x] Wrap symbols, RAG, and contract context in `<untrusted_related_files>` with untrusted context preamble.
- [x] Delete `persona_title` and `{persona}` placeholder outright from task prompt templates (`code_review_prompt.md`, `config_review_prompt.md`, `docs_review_prompt.md`) and prompt builder `build_context_review_prompt`.
- [x] Extend `tests/test_review_classification.py:105-152` and assert every `_build_multi_persona_pipeline` agent carries guardrails and exemplars.
- [x] (2) Outcomes & Empty Replies: accept bare `[]` and markdown-fenced `[]` in `parse_review_response` (`src/devops_cli/ai/review_schema.py`) as empty findings `ReviewResult(findings=[], summary="")` to prevent retry loops on valid clean reviews.
- [x] Record persona reply outcomes as `findings`, `empty`, or `unparsed` in `FileReviewPayload.ai_scratchpad` (`persona_replies`, `persona_outcomes`, `unparsed_personas`) and `ReviewProfile` (`profile.json`).
- [x] Degrade file scratchpad stage to `unparsed` (if all unparsed) or `degraded` (if some unparsed) rather than silently marking clean `reviewed`, and log unparsed personas on the console.
- [x] (3) Persona Stats: split comma-joined personas in `_tally_single_session_findings` (`src/devops_cli/commands/review.py`) before incrementing `by_persona_total` and `by_persona_invalidated` counters for `review stats`.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all modified functions.
- [x] Consolidate multiple linear test assertions into structural tuple equality checks.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Results

- Unit Tests: `tests/test_review_classification.py`, `tests/test_review_pipeline.py`, `tests/test_finding_repetition_compression.py`, `tests/test_review_profile.py`, `tests/test_review.py` all passing.
- Complexity Analysis: `src/devops_cli/ai/review/classification.py`, `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ai/review_schema.py`, and test suites confirmed clean within standard limits ($M \le 10$, depth $\le 5$).
- Gated CI Quality Gate: Full 10-gate validation suite verified.
