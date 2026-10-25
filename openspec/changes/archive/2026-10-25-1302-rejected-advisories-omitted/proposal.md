# Proposal

## Why

Issue #1302: when admission rejects a dependency advisory candidate, `_audit_dep_vulnerability` returns the raw `SavedFinding` instead of omitting it. This behavior breaks the invariant that every reported finding has passed `admit()`. Furthermore, admission does not record the rejection count for rejected advisories because `_admit_advisory_finding` does not pass `rejection_counts`.

## What Changes

- When admission rejects an advisory candidate (`frozen is None`), `_audit_dep_vulnerability` returns `None`. The orchestrator omits the candidate from the reported findings.
- `_admit_advisory_finding` passes `rejection_counts` to `_admit_single_candidate`. Admission records the typed rejection into `rejection_counts`.
- `_write_review_profile` sets the orchestrator rejection counts on the review profiler, so `profile.json` records them.
- Add an automated test in `tests/test_review_admission.py` to verify that a rejected advisory is omitted from the report and counted in the rejections.
- This change alters no behavior that a consumer observes directly through CLI commands or options. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`: `_audit_dep_vulnerability` and `_admit_advisory_finding`.
- `src/devops_cli/ai/review/runner.py`: `_write_review_profile`.
- `tests/test_review_admission.py`: new test verifying omission and counting of rejected advisories.

## Feasibility

- Code inspection at base `1bb164bd`: in `src/devops_cli/ai/review/pipeline.py:2881-2882`, `_audit_dep_vulnerability` executes `if frozen is None: return raw`. When `admit()` rejects an advisory, `frozen` is `None` and `admitted_sf` is `None`. Returning `raw` leaks the rejected finding into the review report.
- In `src/devops_cli/ai/review/pipeline.py:2843-2859`, `_admit_advisory_finding` does not pass `rejection_counts` to `_admit_single_candidate`. Thus `admit()` cannot update the orchestrator's `rejection_counts`.
- Verification with Python 3.14.7: running a test with `DependencySpec(..., line_number=99)` on a one-line file causes `validate_location` to fail with `line-out-of-range`. Returning `None` successfully omits the finding, and passing `rejection_counts` records `{"line-out-of-range": 1}`.

## Existing Tool Considered

The existing `admit()` function in `src/devops_cli/review/admission.py` and `_admit_single_candidate` in `src/devops_cli/ai/review/pipeline.py` already implement validation, suppression, and typed rejection tracking. No new tool or external library is needed. The fix corrects the return path and passes the existing rejection dictionary.
