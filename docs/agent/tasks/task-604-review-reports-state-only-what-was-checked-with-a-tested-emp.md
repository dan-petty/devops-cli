# Task 604: Review Reports State Only What Was Checked, With a Tested Empty Outcome

**Issue**: [#604](https://github.com/dan-petty/devops-cli/issues/604)
**Status**: In Progress
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

The review report asserts checks it never ran. `extract_good_patterns` (`src/devops_cli/ai/review/stages/reporting.py:49-70`) ignores its findings and always emits three fixed patterns, including "cyclomatic complexity <= 10". It adds "zero unpinned critical/high CVEs" and "Zero-Trust Network Isolation" whenever the dependency or network list is empty, and the pipeline always passes lists (`src/devops_cli/ai/review/pipeline.py:2417-2430`); a dependency never queried also defaults to `CLEAN` (`src/devops_cli/models/vulnerability.py:14`). Zero findings read "exceptional engineering quality" (`reporting.py:138-143`); any finding reads "High-priority remediation ... path traversal defenses, and transport protocol safeguards" (`:144-150`). The knowledge base says the section "validates adherence" (`src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md:55`, echoed at `docs/SDLC.md:232`). `devops review pr --post` posts each persona's model-written `positive_observations` and `summary` verbatim (`src/devops_cli/commands/review.py:710-726`, `src/devops_cli/ai/review/runner.py:503-509`), `src/devops_cli/ai/tasks/compose.md:20` asks for praise, and no test covers `--post`. Two null paths already work: empty findings derive `APPROVE` (`tests/test_prompt_programmatic_functions.py:147`) and errored files suppress the clean verdict (`tests/test_review_report_summary.py:123`). vibes gives each harness prompt an explicit refusal clause and bans adjectives standing in for measurements.

### Key Deliverables:

#### Part 1: Report (PR 1)
- [x] **Report Sentences Derived Strictly from Recorded Inputs** (`src/devops_cli/ai/review/stages/reporting.py`):
  - Replaced hardcoded Executive Summary praise ("exceptional engineering quality...") with factual summary stating exact defect count across analyzed files.
  - Derived recommendation sentence dynamically from actual finding themes (`_derive_finding_theme`) and severity breakdown without generic "path traversal defenses" or "transport protocol safeguards".
  - Described a single low finding by its own theme only.
- [x] **Removal of Fixed Good Patterns & Strict Tool Grounding** (`src/devops_cli/ai/review/stages/reporting.py`):
  - Completely deleted the three hardcoded patterns ("Architectural Separation & Invariant Discipline", "Subprocess & Process Execution Safety", "Defensive Typing & Schema Modeling").
  - Omitted `Key Good Patterns Observed` section entirely when no verified tool outputs or positive tool evidence exist.
  - Emitted Supply Chain & Lockfile Integrity pattern only when external dependencies were actually queried with 0 critical/high CVEs.
  - Emitted Network Reference Review pattern stating total, local, and external reference counts.
  - Emitted Static Security Analysis pattern stating count and names of executed analyzers with 0 critical findings.
- [x] **Unqueried Dependency Auditing & Status Tracking** (`src/devops_cli/models/vulnerability.py`, `src/devops_cli/ai/review/pipeline.py`):
  - Defaulted `DependencySpec` to `severity="NOT_QUERIED"`, `security_status="Not Queried"`, and `queried=False`.
  - Updated `_audit_file_dependencies` to mark dependencies as queried clean only if present in `dep_cache`, leaving unqueried packages as `NOT_QUERIED`.
  - Refactored `_format_dependency_table_row` to table-driven dispatch handling `NOT_QUERIED` with `dim` formatting, eliminating `if/elif` ladders and excessive nesting depth.
  - Updated `_format_dependency_summary` to handle unqueried dependency counts.
- [x] **False-Positive Filtering Terminology Alignment**:
  - Replaced misleading "Multi-Agent Adversarial Debate" in console output (`adversarial_debate.py`) and `--no-verification` help text (`help.py`) with "false-positive rule filtering".
  - Updated knowledge base mermaid diagram (`ai_code_review.md`) and SDLC documentation (`SDLC.md`).
- [x] **Unit & Integration Test Invariants** (`tests/test_review_report_summary.py`, `tests/test_review_pipeline.py`, `tests/test_review_verification.py`):
  - Verified a review with no findings and nothing scanned makes no positive claims.
  - Verified a single LOW finding is described by its own theme only.
  - Verified unqueried dependencies default to `NOT_QUERIED` and emit no false good patterns.
  - Verified clean queried dependencies, network reference counts, and executed static analyzers yield concrete patterns.
  - 100% pass across architectural complexity ($M \le 10$, depth $\le 5$) and test suites.

#### Part 2: Post (PR 2)
- [ ] For `--post`, add a fixed, tested zero-findings comment naming the files, personas and analyzers that ran.
- [ ] Remove `positive_observations` from the schema, prompts, merge and renderers with no shim.
- [ ] Post `summary` under a "model notes, not verified" heading.
