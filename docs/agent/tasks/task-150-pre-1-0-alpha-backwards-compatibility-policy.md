# Task 150: Document Pre-1.0 Alpha Status, Zero Backwards Compatibility Guarantee & Post-1.0 SemVer Policy

**Issue**: [#150](https://github.com/dan-petty/devops-cli/issues/150)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

DevOps CLI is active **alpha software** prior to release `1.0.0`. To reach production maturity at a reasonable rate without architectural debt:
1. **Pre-1.0 Alpha Lifecycle & Zero Backwards Compatibility**: Prior to release `1.0.0`, there is no intention of maintaining backwards compatibility.
2. **Ruthless Elimination of Legacy Remnants**: The codebase must remain clean of legacy references, obsolete shims, deprecated code, and compatibility remnants at all times.
3. **Post-1.0 Semantic Versioning & Enterprise Change Management**: Any version after `1.0.0` will strictly follow Semantic Versioning (SemVer 2.0.0) and employ all change management best practices, including feature flags, structured deprecation cycles, and automated migration tooling.

---

## 2. Planned Changes

1. **Agent Instructions (`AGENTS.md`)**:
   - Add explicit core engineering principle on Pre-1.0 Alpha Status, Zero Backwards Compatibility Guarantee, and Post-1.0 SemVer / Enterprise Change Management.
   - Re-enforce zero legacy remnants and ruthless removal of obsolete code to accelerate path to maturity.
2. **Pointer Files (`CLAUDE.md`, `.github/copilot-instructions.md`)**:
   - Ensure pointer headers explicitly highlight the pre-1.0 alpha status and zero legacy remnants mandate.
3. **Core Documentation**:
   - `README.md`: Add a prominent "Software Maturity & Versioning Policy" section.
   - `RELEASE_CYCLE.md`: Update Section 1 (Release Philosophy & Versioning Scheme) to detail the pre-1.0 alpha zero backwards compatibility rule vs post-1.0 SemVer change management.
   - `CONTRIBUTING.md`: Add note in Section 1 on pre-1.0 alpha status and zero zombie/legacy code expectations.
   - `docs/ROADMAP.md`: Add core design principle on pre-1.0 velocity and post-1.0 stability.
   - `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`: Add architectural tenet on pre-1.0 lifecycle and zero legacy remnants.
4. **Verification**:
   - Run `devops docs generate --sync-readme` to ensure documentation parity.
   - Run full CI quality gate (`uv run devops ci`).
