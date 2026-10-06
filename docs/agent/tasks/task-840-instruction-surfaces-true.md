# Task: Instruction Surfaces State Only What Agents Are Held To (#840)

**Issue**: [#840](https://github.com/dan-petty/devops-cli/issues/840)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description

Instruction surfaces and documentation must describe only the conventions, gates, and personas that the system actually enforces. Hardcoded gate numbers, misaligned Copilot review scopes, stale issue templates, and silent overwrites in instruction generators are eliminated.

- **Gate Count Elimination**:
  - Eliminated hardcoded gate counts (`10 gates`, `10/10`, `all 10`, `10-point`) across all documentation and model surfaces (`AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `src/devops_cli/ai/knowledge_base/it_domains/`, `src/devops_cli/models/ci.py`, and `src/devops_cli/ai/instruction_generator.py`).
  - Standardized on unified `Gated` quality gate terminology.
- **Copilot Review Rescoping**:
  - Rescoped automatic Copilot review statements to PRs into `main` only across `AGENTS.md`, `docs/SDLC.md`, and `src/devops_cli/ai/instruction_generator.py`, explicitly documenting the monthly token budget rationale.
- **Issue Templates Alignment**:
  - Updated issue templates referenced in `AGENTS.md` to supported templates (`bug_report.yml`, `feature_request.yml`), removing deprecated `security_advisory.yml` and `task.yml`.
- **Instruction Generator Safety & Guard**:
  - Added `--force` option to `devops ai agents` (`src/devops_cli/commands/ai.py` and `src/devops_cli/lang/en/help.py`).
  - `devops ai agents` writes pointer stubs (`CLAUDE.md`, `.github/copilot-instructions.md`) and leaves an existing `AGENTS.md` untouched unless `--force` is provided, exiting non-zero (code 1) without calling the LLM.
  - Removed vestigial `_pointer_stub` helper function from `src/devops_cli/commands/ai.py`.
  - Regenerated `CLAUDE.md` and `.github/copilot-instructions.md` matching generator output.
- **Offline Assertion Test Suite**:
  - Added `tests/test_agents_md_claims.py` verifying that all issue templates named in `AGENTS.md` exist on disk, active personas in `docs/SELF_IMPROVEMENT.md` are valid `Persona` enum values, and instruction stubs are byte-equal to generator output.

## Acceptance Criteria

- [x] No gate count strings (`10 gates`, `10/10`, `all 10`, `10-point`) match in `AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `src/devops_cli/ai/knowledge_base/it_domains/`, `src/devops_cli/models/ci.py`, or `src/devops_cli/ai/instruction_generator.py`.
- [x] Offline test suite `tests/test_agents_md_claims.py` asserts that every issue template named in `AGENTS.md` exists on disk.
- [x] `tests/test_agents_md_claims.py` asserts that every active persona in `docs/SELF_IMPROVEMENT.md` is a member of `Persona`, accepting the line 187 negation of `performance`/`sre`.
- [x] Copilot review statements in `AGENTS.md`, `docs/SDLC.md`, and `src/devops_cli/ai/instruction_generator.py` are scoped to PRs into `main` only, citing the monthly token budget.
- [x] `test_ai_agents_force_guard_and_refusal` in `tests/test_instruction_generator.py` tests that `devops ai agents` leaves existing `AGENTS.md` untouched and exits non-zero without calling the LLM unless `--force` is given.
- [x] Vestigial `_pointer_stub` helper is removed from `src/devops_cli/commands/ai.py`; only `generate_pointer_stub` exists.
- [x] `security_advisory.yml` and `task.yml` are removed from `AGENTS.md`; `performance` and `sre` appear in `docs/SELF_IMPROVEMENT.md` only as the line 187 negation.
- [x] Outdated command references (`pr_create`, `devops pr comment`) and obsolete version numbers are removed from `AGENTS.md`.
- [x] Knowledge base diff under `src/devops_cli/ai/knowledge_base/` touches exactly 2 files (`ruff_mypy_pytest.md` and `continuous_integration_and_progressive_verification.md`).
- [x] `devops ai agents --help` documents `--force`.
- [x] `CLAUDE.md` and `.github/copilot-instructions.md` are byte-equal to `generate_instruction_content(target, parse_project_metadata(repo_root))`.
- [x] `changelog.d/840.md` exists; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- Pending a person: `uv run devops ci` passes on this branch.
