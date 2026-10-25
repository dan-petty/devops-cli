# Design

## Context

See `proposal.md` for background context. During code review execution, the review pipeline orchestrator audits dependency vulnerabilities via `_audit_file_dependencies` and `_audit_dep_vulnerability`. `_audit_dep_vulnerability` calls `_admit_advisory_finding` to admit the advisory candidate against the commit tree. If admission accepts the advisory, `admit()` returns a frozen `Finding`. If a suppression rule matches, `_admit_single_candidate` returns the frozen finding and `None` for the saved finding, omitting it from the report while keeping it in the admitted scanner list. However, if admission rejects the candidate (for example due to an invalid path or a line number out of range), `_admit_single_candidate` returns `(None, None)`. `_audit_dep_vulnerability` incorrectly checked `if frozen is None: return raw`, returning the unadmitted finding to the caller.

## Goals / Non-Goals

**Goals:**

- Ensure an advisory candidate that admission rejects is never returned in reportable findings.
- Ensure rejection of an advisory candidate increments the typed rejection count in `self.rejection_counts`.
- Ensure the profile records the rejection counts.
- Add an automated test that fails before the fix and passes after it.

**Non-Goals:**

- Do not modify how suppressions work for advisories (already handled in #1295).
- Do not alter the admission logic inside `admit()`.

## Decisions

- **Return `None` when `frozen is None` in `_audit_dep_vulnerability`.**
  When admission rejects an advisory, `_admit_advisory_finding` returns `(None, None)`. Returning `None` from `_audit_dep_vulnerability` ensures that `_audit_file_dependencies` does not append the rejected finding to the reportable findings list.
  - *Rejected alternative:* Raise an exception on rejection. That would abort the entire review run instead of gracefully rejecting invalid scanner candidate locations.

- **Pass `rejection_counts` to `_admit_single_candidate` in `_admit_advisory_finding`.**
  `self.rejection_counts` tracks typed rejections on the orchestrator. Passing `rejection_counts=getattr(self, "rejection_counts", None)` allows `admit()` to record rejections such as `line-out-of-range` or `path-not-in-commit`.
  - *Rejected alternative:* Maintain a separate rejection counter for advisories. Tracking rejections uniformly across static tools and dependency advisories keeps reports consistent.

- **Synchronize `rejection_counts` with the active profiler.**
  In `_admit_advisory_finding`, update the active profiler with `rejection_counts` if a profiler is active, and update `_write_review_profile` in `runner.py` to record `orchestrator.rejection_counts`.
  - *Rejected alternative:* Rely only on static scanner rejection synchronization. Dependency auditing runs after static scanners, so subsequent rejections would not reach the profile.

## Risks / Trade-offs

- [An advisory with an inaccurate line number from upstream data is omitted] → This is the intended behavior of the admission gate: findings with invalid locations must not be admitted or reported as reliable review findings.
