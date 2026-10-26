# Proposal

## Why

Issue #1353: `base_fingerprints` receives fingerprints only from static scanners that run on the base revision.
Every dependency advisory is listed as introduced (`baselineState: new`).
This occurs even when the base revision pins the same vulnerable dependency version.
The review report lists the advisory under introduced findings instead of pre-existing findings.

## What Changes

- `_audit_file_dependencies` extracts the base revision pins from the base file content when `self.base_revision` is present.
- It reuses the advisory cache `dep_cache` and makes no extra OSV requests.
- It admits the base dependency advisories against the base content.
- It adds those advisory fingerprints to `self.base_fingerprints`.
- A pre-existing advisory in changed files is marked as unchanged (`baselineState: unchanged`, `introduced: false`).
- It is rendered under `## Pre-existing Findings in Changed Files`.
- A newly introduced pin advisory is marked as new (`baselineState: new`, `introduced: true`) and rendered under `## Introduced Findings`.
- Add an automated test in `tests/test_review_admission.py` verifying that a pre-existing advisory is listed under Pre-existing and a new pin advisory under Introduced.
- This change alters no behavior that a consumer observes directly through CLI commands or options. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`: `_audit_file_dependencies` and helper functions for extracting base pins and admitting base advisories.
- `tests/test_review_admission.py`: new test verifying pre-existing and introduced dependency advisories.

## Feasibility

- Code inspection at `origin/main` (`4776f632`): in `src/devops_cli/ai/review/pipeline.py:2600`, `self.base_fingerprints` is populated only by `_collect_base_revision_fingerprints`.
- `_collect_base_revision_fingerprints` runs only static scanners (`Bandit`, `Semgrep`, `Kube-linter`, etc.).
- In `_audit_file_dependencies` (`pipeline.py:2946`), `self.base_fingerprints` is passed to `_admit_single_candidate` through `_admit_advisory_finding`.
- Because `self.base_fingerprints` contains no advisory fingerprints, every advisory is admitted with `is_preexisting = False` (`baseline_state = "new"`, `introduced = True`).
- When `self.base_revision` is present, `self.base_revision.read(fpath)` provides the base file content.
- `_audit_single_dep(dep, dep_cache)` looks up entries in `dep_cache` in memory without initiating network requests.
- Admitting the base advisory candidate against `base_content` generates `fingerprint_v2`.
- Adding this `fingerprint_v2` to `self.base_fingerprints` allows subsequent admission of the head finding to recognize the advisory as pre-existing.

## Existing Tool Considered

The existing `admit()` function in `src/devops_cli/review/admission.py`, `_admit_single_candidate` and `_build_vulnerability_finding` in `src/devops_cli/ai/review/pipeline.py`, and `packaging.requirements.Requirement` already implement validation, admission, and dependency specification parsing. No new tool or external library is needed.
