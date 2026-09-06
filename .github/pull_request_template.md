## Description
<!-- Provide a concise description of the changes introduced by this pull request and the underlying motivation or problem being resolved. -->

---

## Type of Change
<!-- Mark the relevant option with an 'x'. -->
- [ ] `feat`: New feature or capability
- [ ] `fix`: Bug fix or defect remediation
- [ ] `refactor`: Code reorganization with zero functional behavior change
- [ ] `docs`: Documentation updates or additions
- [ ] `test`: New or updated tests
- [ ] `chore`: Maintenance, dependencies, or tooling updates

---

## Target Base Branch
<!-- In accordance with AGENTS.md, all feature, fix, refactoring, and docs PRs must target the active release branch. -->
- Base branch targeting: `release/v<version>` (not `main`)

---

## Enterprise SDLC Quality Gate Checklist
<!-- Every PR must satisfy the following quality gates prior to maintainer review. -->
- [ ] **Test-First Implementation (TDD)**: Comprehensive unit and integration tests authored before implementation code.
- [ ] **Full CI Quality Gate**: `devops ci` (or `uv run devops ci`) executed locally with 10/10 green quality gates.
- [ ] **Strict Code Coverage**: Maintained strict $\ge 90\%$ code coverage requirement across `src/`.
- [ ] **Architectural Invariants Gate**:
  - [ ] Cyclomatic complexity $\le 10$ project-wide across all functions and closures (`devops scan complexity`).
  - [ ] Maximum nesting depth $\le 5$ (< 6 indentation levels) across all code blocks (`test_no_excessive_nesting_in_src`).
  - [ ] Standardized domain exceptions inheriting from `DevOpsCLIError` with zero bare `ValueError`/`RuntimeError`.
  - [ ] Pytest collection hygiene enforced (`__test__ = False` on dummy/mock models).
- [ ] **Zero-Trust Security & Egress Safety**:
  - [ ] Zero plaintext secrets, API keys, or credentials stored in code, configurations, or commit history.
  - [ ] No information leaked or extracted from private or `.gitignored` paths (`.env*`, `.ssh/`, `.data/`).
  - [ ] SSRF mitigation and bounded subprocess timeouts strictly enforced.
- [ ] **Canonical Location Formatting**: All CLI outputs, Rich tables, reports, and review findings formatted as `filename.ext:n-n`.
- [ ] **Documentation Synchronization**: CLI options, markdown guides, and README synchronized via `devops docs generate --sync-readme`.
- [ ] **Conventional Commit Messages**: Commit history adheres strictly to Conventional Commits format (`feat(scope): ...`, `fix(scope): ...`).

---

## Related Issues / Milestones
<!-- Link any related issues or milestones below (e.g. Closes #123, Refs Milestone v0.2.14). -->
- Related Milestone:
- Related Issues:
