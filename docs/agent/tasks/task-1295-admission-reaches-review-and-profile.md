# Task: Suppressed and Pre-existing Scanner Findings Reach Their review.md Sections, and profile.json Counts Admission Rejections (#1295)

**Issue**: [#1295](https://github.com/dan-petty/devops-cli/issues/1295)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/review

## Description
#871 admits scanner findings and dependency advisories through `admit()`, but the review kept only the admitted severity. Copilot threads 1 and 2 on release PR #1283 were confirmed at 61f9b67 with tests that failed there:
- A finding a `.devops/review.toml` suppression covered stayed reportable and showed under Introduced Findings.
- Pre-existing Findings in Changed Files never rendered, because `SavedFinding` had no `introduced` field.
- The Suppressed Findings section read `admitted_findings`, which nothing sets.
- The production admission never passed `rejection_counts`, so `profile.json` always recorded no rejections.

The admission result now reaches `review.md`, `findings.sarif` and `profile.json`. Admission covers scanner findings and dependency advisories only; findings from the review's models do not pass through `admit()`, and the v0.2.28 release notes say so.

## Key Changes
- **Scanner admission** (`src/devops_cli/ai/review/pipeline.py`):
  - `_admit_single_candidate` returns no `SavedFinding` for a suppressed candidate, so it leaves the reported set. For any other candidate it copies the admitted severity and `introduced` onto the `SavedFinding`.
  - `_admit_scanner_findings` keeps every admitted frozen finding, suppressed ones included, in `admitted_scanner_findings`, which `findings.sarif` and the Suppressed Findings section are written from.
  - Both helpers forward `rejection_counts` to `admit()`. `_run_static_scanners` counts the head-revision rejections and passes them to the profiler's `set_rejections`. The base-revision admission does not count, because its candidates are not this review's.
- **Advisory admission** (`src/devops_cli/ai/review/pipeline.py`): `_audit_dep_vulnerability` records a suppressed advisory in `admitted_scanner_findings` and returns None, which `_audit_file_dependencies` skips. An advisory that admission rejects is still reported as before; that path cannot trigger in shipped flows and is follow-up #1302.
- **Report** (`src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ai/review_schema.py`):
  - `_build_suppressed_findings_section` reads `admitted_scanner_findings`. It lists each suppressed finding by file and line (`location_display`), so two suppressions of one rule in one file stay two rows.
  - `SavedFinding` gains `introduced: bool = True`, which the Introduced and Pre-existing sections already read.

## Acceptance Criteria
- [x] A suppressed scanner finding or dependency advisory leaves the reported set, and is listed under Suppressed in `review.md` and in SARIF through `admitted_scanner_findings` (`test_review_toml_suppressed_scanner_finding_is_listed_not_reported`, `test_suppressed_dependency_advisory_is_listed_not_reported` in `tests/test_review_admission.py`).
- [x] A finding whose fingerprint is in the base revision is listed under Pre-existing through `SavedFinding.introduced` (`test_scanner_finding_at_a_base_fingerprint_is_listed_as_preexisting`).
- [x] Head-revision admission rejections reach `profile.json` through `set_rejections` (`test_head_revision_admission_rejections_reach_the_profile`).
- [x] Each of these tests fails at 61f9b67.
- [x] `changelog.d/1295.md` records the change and says that admission covers scanner findings and dependency advisories; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Release process: before #1283 merges, the v0.2.28 section of `CHANGELOG.md` takes this fragment and narrows the #871 entry from "Every reported review finding is admitted" to scanner findings and dependency advisories, through a `chore/open-v0.2.28-<slug>` pull request.
