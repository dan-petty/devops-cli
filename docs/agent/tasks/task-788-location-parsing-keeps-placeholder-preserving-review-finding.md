# Task 788: Location Parsing Keeps Placeholder, Preserving Review Finding

**Issue**: [#788](https://github.com/dan-petty/devops-cli/issues/788)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/review`, `priority/p2-medium`
**Feasibility**: Verified against real system: confirmed in security/bandit.py:74 and security/semgrep.py:202-209 that scanner findings carry absolute paths that leak into findings.json and review.md. Tested that relativizing paths against scan root/worktree ensures clean relative locations and descriptions.

---

## 1. Description & Objectives

Static security scanner findings from Semgrep and Bandit carry absolute filesystem paths (`/workspaces/devops-cli/...`), leaking host environment and container workspace details into `findings.json`, `review.md`, and pull request review comments. Under the evidence-first review redesign (#1137), tool-layer findings must carry clean repository-relative paths (`app/x.py:12`), with no absolute paths embedded in findings locations or descriptions.

#### Key Deliverables:
- Semgrep and Bandit scanner findings carry paths relative to the scan root (`app/x.py:12` rather than absolute paths).
- Review pipeline static-scan step normalizes candidate findings to repository-relative paths before admission and reporting.
- Fake results with absolute paths come out as `src/app.py:12` in `findings.json` and `review.md`, with no absolute path in the description.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Acceptance Criteria
- [x] Semgrep and Bandit findings carry paths relative to the scan root; a test with a fixture tree shows `app/x.py`, not an absolute path.
- The persona-location criteria above are not built; they close with this item, as covered by #871.
- [x] Fake results with absolute paths come out as `src/app.py:12` in `findings.json` and `review.md`, with no absolute path in the description; offline.
- [x] A test passes fake Semgrep and Bandit results with absolute paths through the review's static-scan step and asserts `src/app.py:12`.
- [x] Offline tests add at most 1 s; `changelog.d/788.md`; `uv run devops ci` passes.
