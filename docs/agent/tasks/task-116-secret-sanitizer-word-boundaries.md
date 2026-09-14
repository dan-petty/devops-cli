# Task 116: Secret Sanitizer Regex Word Boundary Hardening & Artifact Name Guard

**Issue**: [#116](https://github.com/dan-petty/devops-cli/issues/116)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.18`
**Priority**: `priority/p0-critical`
**Scope**: `scope/security`

---

## 1. Description & Architectural Objectives

Harden regex patterns and boundary guards in `devops_cli.security.sanitizer` to eliminate false-positive secret masking:
1. **Regex Word Boundary Hardening**:
   - Enforce boundary anchors `\bsk-[A-Za-z0-9_-]{20,}\b` and `\bsk-ant-[A-Za-z0-9_-]{20,}\b` in `_SECRET_PATTERNS`.
   - Prevent trailing substring matching inside non-secret words or punctuation.
2. **Safe Filesystem Paths & Artifact Name Guard**:
   - Distinguish genuine secret literals from safe filesystem paths, file extensions (`.md`, `.py`, `.json`, `.yaml`, `.yml`, `.sh`, `.toml`, `.txt`), and artifact identifiers.
   - Guard filenames starting with `task-` or containing path separators from being corrupted into `<masked-*>` tokens.
3. **Engineering Standards & Architectural Invariants**:
   - Strict cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ project-wide.
   - 100% test pass on secret masking and zero regressions in `devops ci`.

---

## 2. Planned Changes

1. **`src/devops_cli/security/sanitizer.py`**:
   - Update OpenAI and Anthropic secret regex patterns with boundary anchors `\b...` and negative boundary lookarounds.
   - Implement path and extension checks or pre/post-match filters to ensure safe filenames (e.g. `task-*.md`, paths containing `/`) and compound non-secret identifiers are preserved intact while genuine API tokens (including hyphenated/underscore-prefixed secrets like `prefix-sk-...`) are still cleanly redacted.
2. **`tests/test_consolidation_security_sanitizer.py`**:
   - Add unit tests covering:
     - Compound `task-*` filenames and paths (e.g. `docs/agent/tasks/task-090-infracost-finops-cloud-cost.md`, `task-sk-something.md`).
     - Genuine OpenAI and Anthropic keys with various prefixes and delimiters.
     - Filesystem paths with standard extensions (`.py`, `.md`, `.json`, `.yaml`).

---

## 3. Verification & Acceptance Criteria

- [x] Zero false masking of `task-*` filenames across reviews and artifacts.
- [x] Genuine API keys (OpenAI `sk-...`, Anthropic `sk-ant-...`, GitHub `ghp_...`, Vault `hvs....`, etc.) remain 100% redacted.
- [x] All unit tests in `tests/test_consolidation_security_sanitizer.py` pass cleanly.
- [x] `devops ci` quality gates pass with $\ge 90\%$ code coverage.
