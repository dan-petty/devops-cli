# Design

## Context

See `proposal.md` for background context.
During code review execution, `ReviewPipelineOrchestrator._audit_file_dependencies` audits dependency vulnerability findings for a file against `dep_cache`.
When `self.base_revision` is available, static scanner fingerprints from the base commit are collected into `self.base_fingerprints`.
However, base dependency pins were not audited or admitted into `self.base_fingerprints`.
Consequently, any vulnerable dependency that existed in the base revision is reported as introduced.

## Goals / Non-Goals

**Goals:**

- When `self.base_revision` is present and contains the target file, extract the base revision dependency pins.
- Re-use `dep_cache` to find known vulnerabilities for each base dependency pin without performing extra network requests.
- Admit the base advisory candidate against the base file content to compute its stable `fingerprint_v2`.
- Add the admitted base advisory fingerprint to `self.base_fingerprints`.
- Ensure head advisory candidates matching base revision pins are admitted with `baseline_state="unchanged"` and `introduced=False`.
- Add an automated test that fails before the fix and passes after it.

**Non-Goals:**

- Do not perform network requests or query remote OSV endpoints for base revision dependencies.
- Do not append base revision advisory findings to `self.admitted_scanner_findings` or reported findings.
- Do not modify how suppression markers work for advisories.

## Decisions

- **Extract pinned dependencies from base content.**
  Parse lines containing exact pins (`==` or `===`) using `Requirement` or pattern matching, recording line numbers in `DependencySpec`.
  - *Rejected alternative:* Re-running package manager binaries. Running external tools is slow and requires lockfile installations that may not exist in base revision files.

- **Re-use `dep_cache` without extra queries.**
  Evaluate base pins strictly against the provided `dep_cache` via `_audit_single_dep`.
  - *Rejected alternative:* Querying OSV for base pins not present in `dep_cache`. The acceptance criteria forbids extra OSV requests.

- **Admit base candidates in-memory.**
  Invoke `_admit_single_candidate` with `file_content_getter` returning `base_content` and `commit_files` containing `fpath`.
  - *Rejected alternative:* Writing base files to temporary directories on disk. In-memory content getter is faster and requires no disk operations.
