# Task 587: Mitigated Findings Re-Verified When Their Perimeter Changes

**Issue**: [#587](https://github.com/dan-petty/devops-cli/issues/587)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

A MITIGATED finding (`src/devops_cli/ai/review_schema.py:370-371`), set by the verifier (`ai/review/verification.py:1134-1149`) or `devops review verify --status MITIGATED` (`commands/review.py:896-908`), is `reportable=False` and dropped from the merge recommendation (`review_schema.py:793`). Nothing records what mitigates it: the updates dict at `verification.py:1171-1181` discards the verifier's `reason`, and no field names the mechanism or its file. The only file-keyed cross-session store (`ai/review/common_hallucinations.py:966` `auto_record_invalidated_finding`) writes only on INVALIDATED. Neither `devops review` (`ai/review/runner.py:1583-1645`, `:1646-1680`) nor `devops pr check-readiness` (`commands/pr.py:1304-1393`) intersects the diff with mitigations.

#### Key Deliverables:
- [x] Record mitigation data on `Finding`: `mitigating_mechanism: str | None`, `perimeter_files: list[str]`, and optional `regression_test: str | None`.
- [x] Verifier prompt (`src/devops_cli/ai/tasks/verify_finding_system.md`) requires both `mitigating_mechanism` and `perimeter_files` for `mitigated: true`; degrades to `UNVERIFIED` (`reportable=False`) if either is omitted or empty.
- [x] Prohibit `mitigated=True` on `INVALIDATED` findings across verdict updates and architectural invariant checkers.
- [x] Enhance `devops review verify --status MITIGATED` with repeatable `--perimeter <path>`, mitigation reason, and optional `--regression-test <path>`.
- [x] Track human-accepted mitigations in persistent ledger (`src/devops_cli/ai/review/mitigated_findings.json` via `mitigations.py`); model-only verdicts remain session-local.
- [x] Measure before enforcing: `devops review branch|pr` and `_evaluate_pr_blockers` intersect diff with ledger `perimeter_files` and warn `'N mitigated finding(s) whose perimeter changed'`, naming each, with zero exit-code change.
- [x] Correct the `Executable Verification Criteria` entry in `docs/ROADMAP.md` regarding execution sandbox (`HostSandbox` / `WorkloadSandboxRunner`).
- [x] Unit and integration test coverage with structural tuple equality assertions.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ project-wide.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
