# Task 169: Require Concise Commit Messages Stating Direct Effect of Change

**Issue**: [#169](https://github.com/dan-petty/devops-cli/issues/169)
**PR**: None
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Establish clear repository instructions and documentation mandating that AI agents and contributors author concise commit messages stating simply and directly the effect of each specific change.

### Key Objectives
1. **Concise, Effect-Driven Commit Messages**:
   - Commit messages must simply state what the change directly accomplishes.
   - Prohibit overly verbose summaries, sprawling lists, compound multi-clause sentences, and redundant narrative preambles in commit subjects.
2. **Elimination of Arbitrary Internal Metadata**:
   - Reiterate prohibition of internal review timestamps, session numbers, subagent identifiers, or prompt phase numbers in commit messages and PR titles.
3. **Repository Instruction & Template Alignment**:
   - Verify alignment across canonical [`AGENTS.md`](../../../AGENTS.md), [`src/devops_cli/ai/instruction_generator.py`](../../../src/devops_cli/ai/instruction_generator.py), [`docs/ROUTINE_TASKS.md`](../../../docs/ROUTINE_TASKS.md), and [`docs/SDLC.md`](../../../docs/SDLC.md).
   - Ensure automated unit test coverage in [`tests/test_instruction_generator.py`](../../../tests/test_instruction_generator.py).

---

## 2. Planned Changes

1. **`AGENTS.md`**:
   - Section 3 ("Git Hygiene, Release Governance & GitHub Integration") under *Commit Standards* explicitly mandates concise, effect-driven commit messages.
2. **`src/devops_cli/ai/instruction_generator.py`**:
   - Scaffolding template generates canonical commit guidelines mandating concise effect-driven messages.
3. **`docs/ROUTINE_TASKS.md` & `docs/SDLC.md`**:
   - Document commit standards and message hygiene under Cadence B / Feature PR Lifecycle.
4. **`tests/test_instruction_generator.py`**:
   - Validate that generated agent instructions enforce concise commit messages.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#169) with `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-169-concise-commit-messages.md`.
- [x] Checkout dedicated topic branch `docs/169-concise-commit-messages`.
- [x] Update `AGENTS.md` commit standards.
- [x] Update `src/devops_cli/ai/instruction_generator.py`.
- [x] Update `docs/ROUTINE_TASKS.md` and `docs/SDLC.md`.
- [x] Verify unit tests in `tests/test_instruction_generator.py`.
- [ ] Run full CI quality gate (`devops ci`).
- [ ] Open Pull Request targeting `release/v0.2.17`.
- [ ] Monitor CI checks, transition to ready, verify merge readiness, and squash-merge into `release/v0.2.17`.
