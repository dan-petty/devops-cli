# Task 103: Generalize devops ai review for Arbitrary Target Repositories & Multi-Convention Discovery

**Issue**: [#103](https://github.com/dan-petty/devops-cli/issues/103)
**Active Release Milestone**: `v0.2.15`
**Status**: Done
**Scope**: `src/devops_cli/ai/` (`personas/`, `tasks/`, `review/runner.py`, `review/pipeline.py`), `tests/test_review_path.py`

---

## 1. Description & Architectural Objectives

`devops ai review` is a universal, target-agnostic project code review tool. It must evaluate any target codebase (Python, Go, Rust, TypeScript, monorepos, Kubernetes manifests, etc.) objectively according to universal software engineering principles (OWASP Top 10, CIS benchmarks, SOLID, Clean Architecture) and the target project's declared conventions rather than assuming or enforcing `devops-cli` internal functions (`mask_secrets`), internal variables (`_MAX_OVERFLOW_FALLBACK_ENTRIES`), or FastMCP tool identifiers (`scan_trivy`, `scan_kubelinter`).

### Key Deliverables
1. **Target-Agnostic Persona Prompts**:
   - `src/devops_cli/ai/personas/devsecops/prompt.md`: Generalize static scanner list to industry-standard tool families and remove internal function names (`mask_secrets`) and CLI-specific output assumptions.
2. **Target-Agnostic Finding Verification Engine**:
   - `src/devops_cli/ai/tasks/verify_finding_system.md`: Replace internal variable names (`_MAX_OVERFLOW_FALLBACK_ENTRIES`), specific sandbox symbols (`safe_builtins`), and library constructor specifics (`httpx2.Timeout`) with universal architectural invariants (bounded cache sizes, reflection isolation in evaluation sandboxes, and positional default interfaces).
3. **Multi-Ecosystem Convention References in Tasks**:
   - `src/devops_cli/ai/tasks/path_review_prompt.md`, `diff_review_prompt.md`, `code_review_prompt.md`, `review.md`: Explicitly mention multi-convention sources (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`).
4. **Multi-Convention Discovery in Pipeline & Runner**:
   - `src/devops_cli/ai/review/runner.py` (`_load_agents_md`) and `src/devops_cli/ai/review/pipeline.py` (`_read_target_conventions`): Inspect candidate convention files in priority order (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.cursor/rules`) so that any repository's instructions are honored automatically.
5. **Unit & Invariant Verification**:
   - Add tests in `tests/test_review_path.py` asserting conventions loading from alternative files like `CLAUDE.md`.
   - Ensure all 10 quality gates pass via `devops ci`.

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#103) with milestone `v0.2.15`.
- [x] Refactor `src/devops_cli/ai/personas/devsecops/prompt.md` to be completely target-agnostic.
- [x] Refactor `src/devops_cli/ai/tasks/verify_finding_system.md` to eliminate host-project variables and specific symbols.
- [x] Refactor review task prompts in `src/devops_cli/ai/tasks/` (`code_review_prompt.md`, `diff_review_prompt.md`, `path_review_prompt.md`, `review.md`).
- [x] Enhance `runner.py` and `pipeline.py` to discover conventions across `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursorrules`.
- [x] Update and expand unit tests in `tests/test_review_path.py`.
- [x] Run `devops ci` quality gate.
- [x] Atomic commit and push to `release/v0.2.15`.
