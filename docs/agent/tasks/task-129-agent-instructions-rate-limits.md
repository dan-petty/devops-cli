# Task 129: Update Agent Instructions to Honor API Rate Limits and Quotas

**Issue**: [#129](https://github.com/dan-petty/devops-cli/issues/129)
**PR**: [#130](https://github.com/dan-petty/devops-cli/pull/130)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p2-medium`
**Scope**: `scope/ai`

---

## 1. Description & Architectural Objectives

AI agents (Claude, GitHub Copilot, Cursor, Codex) interacting with external APIs (GitHub REST/GraphQL, LLM inference endpoints, container registries, Valkey/Qdrant, and remote observability backends) can encounter HTTP 429 Too Many Requests, secondary rate limits, or GraphQL node/complexity exhaustion during high-frequency operations, batch scans, and multi-step reviews. Currently, `AGENTS.md` and `src/devops_cli/ai/instruction_generator.py` lack explicit instructions directing AI agents to proactively inspect, respect, and adapt to API rate limits.

### Key Deliverables
1. **Canonical Agent Instructions Update (`AGENTS.md`)**:
   - Add explicit core engineering principle in Section 1: *API Rate Limit Honor & Resilient Backoff*.
   - Add detailed operational guidance in Section 3 under *GitHub Projects, Issues, Views, Milestones & Label Governance*:
     - Proactive inspection of GitHub rate limits via `gh api rate_limit` and `x-ratelimit-*` headers.
     - Adaptive fallback from GraphQL rate-limiting to REST endpoints (`gh api repos/...`).
     - Exponential backoff with jitter and honoring `Retry-After` reset windows.
     - Client-side caching and avoidance of aggressive polling loops.
   - Add guidance in Section 4/5 for AI/LLM inference endpoints (TPM/RPM budgeting, concurrency limits, and retry backoff).
2. **Instruction Generator Template Synchronization (`src/devops_cli/ai/instruction_generator.py`)**:
   - Update `DEVOPS_CLI_AGENTS_METADATA_TEMPLATE` with the rate-limiting best practices so newly generated/scaffolded instructions stay synchronized with canonical guidelines.
3. **Unit Tests & Verification**:
   - Update tests in `tests/test_instruction_generator.py` to assert presence of rate-limit guidance.
   - Verify `devops docs check` passes cleanly with zero drift.
   - Run full `pytest tests/test_instruction_generator.py`.

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#129) with milestone `v0.2.16`.
- [x] Create dedicated topic branch `docs/agent-instructions-rate-limits`.
- [x] Create task tracking document `docs/agent/tasks/task-129-agent-instructions-rate-limits.md`.
- [x] Update `AGENTS.md` with comprehensive API rate limiting rules across core engineering, GitHub integration, and AI inference.
- [x] Update `src/devops_cli/ai/instruction_generator.py` to include rate-limiting guidance in scaffolded templates.
- [x] Update and run unit tests in `tests/test_instruction_generator.py`.
- [x] Verify documentation integrity via `devops docs check`.
- [x] Commit, push to `origin/docs/agent-instructions-rate-limits`, and open Pull Request targeting `release/v0.2.16`.
