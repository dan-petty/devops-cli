# Task 165: Require Draft Pull Requests for In-Progress Work

**Issue**: [#165](https://github.com/dan-petty/devops-cli/issues/165)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/docs`

---

## 1. Description & Architectural Objectives

Establish an explicit policy and agent instruction mandating that whenever AI agents or contributors open pull requests that are not yet fully implemented, tested, and ready for review, they must be opened as **Draft Pull Requests** (`gh pr create --draft` or passing `draft: true`).

### Key Objectives
1. **Mandatory Draft PRs for In-Progress Deliverables**:
   - Prevent premature review cycles and unready CI review notifications.
   - Avoid false merge-readiness assumptions while maintaining compliance with the zero orphan remote branches requirement.
2. **Clear Lifecycle Transition Protocol**:
   - Explicitly define the transition from draft to ready for review (`gh pr ready <number>` or GraphQL mutation `markPullRequestReadyForReview`) once all implementation code, tests ($\ge 90\%$ coverage), and documentation are complete.
3. **Repository Instruction Alignment**:
   - Update canonical [`AGENTS.md`](../../../AGENTS.md).
   - Update instruction generator template in [`src/devops_cli/ai/instruction_generator.py`](../../../src/devops_cli/ai/instruction_generator.py).
   - Update [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) and [`docs/ROUTINE_TASKS.md`](../../../docs/ROUTINE_TASKS.md).
   - Add unit tests in [`tests/test_instruction_generator.py`](../../../tests/test_instruction_generator.py).

---

## 2. Planned Changes

1. **`AGENTS.md`**:
   - Add explicit requirement in Section 3 ("Git Hygiene, Release Governance & GitHub Integration") under *Pull Request Governance & Title Conventions* and *Strict Remote Branch Lifecycle & PR Governance*.
   - Update Section 2 ("Development Workflow & Progressive Verification") under *Modular Per-Task Tracking Architecture* to clarify draft PR creation during `In Progress (WIP)` status.
2. **`src/devops_cli/ai/instruction_generator.py`**:
   - Include draft PR requirement in the generated `AGENTS.md` template for target repositories.
3. **`tests/test_instruction_generator.py`**:
   - Add assertions verifying that generated agent instructions enforce draft PR creation for in-progress work.
4. **`CONTRIBUTING.md` & `docs/ROUTINE_TASKS.md`**:
   - Document draft pull request commands and best practices.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#165) and set status to `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-165-require-draft-prs-for-in-progress-work.md`.
- [x] Create dedicated topic branch `docs/165-require-draft-prs-for-in-progress-work`.
- [x] Update `AGENTS.md` with draft pull request instructions.
- [x] Update `src/devops_cli/ai/instruction_generator.py`.
- [x] Add unit tests in `tests/test_instruction_generator.py`.
- [x] Update `CONTRIBUTING.md` and `docs/ROUTINE_TASKS.md`.
- [ ] Run test suite and full CI quality gate (`devops ci`).
- [ ] Open Pull Request targeting `release/v0.2.17`.
