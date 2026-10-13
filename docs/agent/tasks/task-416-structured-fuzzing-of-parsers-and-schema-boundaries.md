# Task 416: Structured Fuzzing of Parsers and Schema Boundaries

**Issue**: [#416](https://github.com/dan-petty/devops-cli/issues/416)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`
**Feasibility**: Verified against real parser implementations in the codebase: Hypothesis 6.168.3 is installed (`pyproject.toml:84`), `security/sarif.py` lines 238, 474, 508, `core/cleanup.py` lines 76-88, `ci/cache.py` lines 164-185, `argo/gitops.py` lines 228-233, and `ai/review_schema.py` line 1519. Parsers run in microseconds; property tests execute well within the 1-second suite budget.

---

## 1. Description & Objectives

The failures found by hand this release were nearly all boundary cases in parsing and path handling: `Path.relative_to` accepting `..`, `fnmatch` reading `[host]:port` as a character class, `lstrip("./")` stripping a character set, porcelain output shifted by one stripped space. Each was found by reading code. Each is the kind of input a property test generates in seconds.

This deliverable adds structured property-based tests grounded in official specifications across five parsing surfaces: SARIF 2.1.0 documents, git worktree porcelain output, git status porcelain v1 output for cache fingerprinting, git status porcelain output for Argo drift events, and LLM review JSON parsing. Each test function docstring cites the exact specification clause. Discovered edge cases are preserved as permanent `@example` regression cases. Tests mirror the source tree directory structure and add under 1 second total runtime.

#### Key Deliverables:
- [x] Property-based tests for SARIF 2.1.0 parsing (`src/devops_cli/security/sarif.py`) in `tests/security/test_sarif_fuzzing.py` citing SARIF 2.1.0 specification clauses (§3.2.7, §3.14, §3.27, §3.28).
- [x] Property-based tests for git worktree porcelain parsing (`src/devops_cli/core/cleanup.py`) in `tests/core/test_cleanup_fuzzing.py` citing git-worktree(1) porcelain format specification.
- [x] Property-based tests for git status porcelain v1 parsing (`src/devops_cli/ci/cache.py`) in `tests/ci/test_cache_fuzzing.py` citing git-status(1) porcelain v1 format specification.
- [x] Property-based tests for git status drift parsing (`src/devops_cli/argo/gitops.py`) in `tests/argo/test_gitops_fuzzing.py` citing git-status(1) specification and manifest path traversal security invariants.
- [x] Property-based tests for review JSON parsing (`src/devops_cli/ai/review_schema.py`) in `tests/review/test_review_json_fuzzing.py` citing the review JSON schema specification.
- [x] Every property test docstring cites its grounding specification clause.
- [x] Edge-case regression examples preserved with `@example` decorators.
- [x] Fast property settings (`max_examples` tuned) ensuring tests add $\le 1$ second to total suite runtime.
- [x] Changelog fragment `changelog.d/416.md`.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
