# Task: Item refinement to ready with proposed design, tasks and acceptance criteria (`devops roadmap refine`) (#744)

**Issue**: [#744](https://github.com/dan-petty/devops-cli/issues/744)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/feature, scope/roadmap, priority/p1-high

## Description

`devops roadmap refine` evaluates New roadmap items and refines them into Ready status with proposed design, tasks, and acceptance criteria. It inspects local git checkouts, gathers repository context (`CONTEXT.md`, ADRs, cited files and line ranges, identifiers), conducts external technical research (via Tavily search for public repositories), generates a structured refinement proposal using model calls, and deterministically validates all cited sources and owner decisions before writing to GitHub.

- **Selection**: Selects items nearest place first, each place by priority rank (#1515): the current release's New items, each planned release's, nearest first, then the backlog's P0 and P1 items; in a planned release and among the backlog's P0 and P1 items also Ready items with no refine record. Then other New backlog items while fewer than the configured `release_cap` (default 12) items are Ready across the next planned release and the backlog. Skips Blocked or started items. Skips unchanged items (matching `refine.body_hash` and `refine.section_hash`); re-picks items when the issue body changes. Skips an item whose section a person edited (`check_person_edits`) before it takes a place.
- **Context minimization**: Reads `CONTEXT.md`, `docs/adr/*.md`, cited files and ranges (`git show <sha>:<path>`), and backticked identifiers (`git grep ... <sha>`) using git argv without shell execution. Truncates content within the context window for task `analysis`.
- **Model research & proposal**: Two structured steps via `chat_structured` with `ai.for_task("analysis")`:
  1. Research plan: generates $\le 3$ queries run through Tavily (5 results each) when the repository is public and `TAVILY_API_KEY` is configured.
  2. Proposal: structured `RefinementProposal` (`extra="forbid"`) with problem statement, acceptance criteria with verification, key questions (fact/decision + sources), single-PR fit (or split-offs), suspected block, and dependencies.
- **Deterministic validation**: Validates cited paths and line numbers at the target commit SHA, URLs against Tavily results, and `#N` against store issues. Missing sources for fact answers become open questions. Unanswered questions in the body's `## Key questions` become open questions. Decision answers quote `## Owner decisions` or are marked `(proposed)`.
- **Ready transition**: Moves items New → Ready when complete (problem non-empty, 1+ criteria with verification, 0 open questions, fits 1 PR, no block) with a reason comment naming the commit SHA.
- **Section rendering & person edit guards**: Writes plain-text markdown between markers `<!-- devops-roadmap-refine:start -->` and `<!-- devops-roadmap-refine:end -->` stripped of HTML tags and images, with `@handles`, unknown `#N`, and unallowed URLs wrapped in code spans. Protects against manual edits by verifying section hash and unrecorded sections. Guards against bodies exceeding 65,536 characters.
- **Oversized items & reprioritization**: Items that do not fit one PR remain New, receive `refine.needs_split="true"`, and post a split comment. `devops roadmap reprioritize` descopes them from the current release.
- **Intake hook & runner adapter**: Wired to `apply_intake` to refine admitted critical fixes and P0 features. Added `refine` row to `DEFAULT_DUE_TABLE` in `src/devops_cli/roadmap/run.py` with `needs_clone=True`.
- **CLI & FastMCP mirror**: `devops roadmap refine` supports `--repo`, `--ref`, `--source`, `--item`, `--limit`, `--dry-run`, and `--confirm`. FastMCP mirror `roadmap_refine` provides dry-run inspection without confirm.

## Acceptance Criteria

- [x] **Command options & validation**: `tests/test_roadmap_refine.py::test_inspect_checkout_origin_match_and_mismatch` and `test_cli_refine_dry_run_and_confirm` verify `--repo`, `--ref`, `--source`, `--item`, `--limit`, `--dry-run`, and `--confirm`. Exits non-zero without model calls or writes when checkout origin doesn't match `--repo`.
- [x] **Selection**: `tests/test_roadmap_refine.py::test_selection_next_release_backlog_priorities_and_cap` and `test_selection_skips_unchanged_items_and_picks_on_change` verify selection by priority, cap enforcement (12 Ready items), skipping Ready/Blocked/started items, and skipping unchanged body hashes.
- [x] **Context minimization**: `tests/test_roadmap_refine.py::test_collect_context_and_truncation` verifies gathering `CONTEXT.md`, ADRs, cited files/lines, grep identifiers, and truncation to context budget.
- [x] **Research step**: `tests/test_roadmap_refine.py::test_research_plan_public_vs_private_and_errors` verifies Tavily queries run only for public repositories with API keys, and records error categories on failure.
- [x] **Proposal validation**: `tests/test_roadmap_refine.py::test_validate_proposal_sources_and_questions` verifies path/line citations, fact answers without sources converting to open questions, owner decision quotation, and body key questions.
- [x] **Ready check**: `tests/test_roadmap_refine.py::test_check_ready_matrix` verifies completeness rules (problem statement, criteria with verification, zero open questions, fits one PR, no block).
- [x] **Plain-text markdown renderer & sanitization**: `tests/test_roadmap_refine.py::test_sanitize_text_markdown` verifies stripping HTML tags and images, wrapping handles and unallowed URLs in code spans, and marker boundary preservation.
- [x] **Person edits guard**: `tests/test_roadmap_refine.py::test_person_edits_guards` verifies refusal to overwrite when section hash differs or untracked section exists.
- [x] **Size limit guard**: `tests/test_roadmap_refine.py::test_size_limit_guard` verifies refusal and skip when body would exceed 65,536 characters.
- [x] **Too big item splitting & reprioritization**: `tests/test_roadmap_refine.py::test_too_big_needs_split_and_reprioritize_descopes` verifies `refine.needs_split="true"`, split comments, and reprioritization descoping.
- [x] **Intake hook**: `tests/test_roadmap_refine.py::test_intake_hook_calls_refine` verifies hook trigger on admitted critical fixes and P0 features.
- [x] **Due table & MCP mirror**: `tests/test_roadmap_refine.py::test_run_due_table_refine_adapter` and `tests/test_fastmcp_contracts.py` verify due table runner integration and FastMCP tool contract.
- [x] **CI Quality Gate**: `uv run devops ci` completes with all quality checks passing.
- - Pending a person: `devops roadmap refine --repo <owner>/<repo> --item <N> --dry-run` to inspect proposed refinement plan against a live issue.
- - Pending a person: `devops roadmap refine --repo <owner>/<repo> --item <N> --confirm` to apply refinement and observe issue body update and status transition to Ready on the GitHub board.

## Decisions and deviations

- **Context collection via git argv**: All git operations (`git cat-file`, `git show`, `git grep`, `git rev-parse`) run via `run_subprocess` using argument lists without invoking a shell, ensuring POSIX safety and preventing shell injection.
- **Tavily search abstraction**: `tavily_search` in `src/devops_cli/ai/common_tools.py` provides resilient query execution with bounded timeouts, HTTP status classification, and graceful degradation when the service is unreachable.
- **Unified refine marks**: `RefineRecordKey` (`refine.body_hash`, `refine.section_hash`, `refine.needs_split`) stored in issue `job_record` to maintain idempotency and coordinate with `devops roadmap reprioritize`.
