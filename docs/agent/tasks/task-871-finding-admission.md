# Task: Finding Admission, Anchors, and Evidence-First Review Spine (#871)

**Issue**: [#871](https://github.com/dan-petty/devops-cli/issues/871)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p0-critical
**Scope**: scope/review

## Description
Prior to this change, review findings did not record their producer anchor, scanner output was stamped with generic personae, and model hallucinations or invalid file paths (such as `app/shell.py`) could reach the top of review reports. Furthermore, inline markers added by a change could inadvertently suppress that change's own findings, and `profile.json` and `findings.json` could disagree on counts.

To ensure non-negotiable provenance, strict location integrity, and reproducible evidence-first reviews:
1. Created the isolated review spine package `src/devops_cli/review/` with 0 model imports, encapsulating immutable findings, anchors, location validation, fingerprinting v2, pure severity derivation, state transitions, and suppression matching.
2. Enforced by architectural invariant test that a frozen `Finding` is constructed exclusively by `devops_cli.review.admission.admit()`.
3. Implemented `Anchor` protocol with `ToolAnchor` and `AdvisoryAnchor` to record the exact producing tool run or advisory DB snapshot.
4. Enforced strict location validation against `git ls-tree -r <commit>`, checking path presence, line bounds, and storing `region_sha256`, while counting typed rejections (`path-not-in-commit`, `line-out-of-range`, `object-not-in-commit`, `file-not-scanned`, `tool-not-run`, `canary-failed`, `no-anchor`) into `profile.json`.
5. Derived severity as a pure function of CVSS/security-severity, rule severity, SARIF level, and `.devops/review.toml` path-class caps.
6. Implemented scanner suppression overrides (Bandit `--ignore-nosec`, Semgrep `--disable-nosem`) and verified that inline markers added by a change keep findings `OPEN` marked with `suppressed_by_change=True`.
7. Added `.devops/review.toml` suppressions for B103 on test suites with reasons and expiry (#1024).
8. Written `findings.sarif` carrying tool, version, rule, fingerprint v2, `logicalLocations`, `partialFingerprints`, and `baselineState`, preserving properties on roundtrip and excluding model output.
9. Rendered consolidated `review.md` sections for `## Introduced Findings`, `## Pre-existing Findings in Changed Files`, and `## Suppressed Findings`.
10. Synchronized `profile.json` and `findings.json` counts.

## Key Changes
- **Review Core Package (`src/devops_cli/review/`)**:
  - `anchors.py`: Defined `Anchor` protocol, `ToolAnchor(run_id, result_index, rule_id)`, and `AdvisoryAnchor(db, snapshot, advisory_id, purl, locked_version)`.
  - `finding.py`: Defined frozen immutable `Finding` Pydantic model with `location_display`.
  - `state.py`: Defined `FindingState` (`OPEN`, `SUPPRESSED`, `FIXED`, `CONFIRMED`), `can_transition`, and `assert_finding_state_invariants`.
  - `location.py`: Implemented `validate_location`, relative path normalization against worktree root, and `compute_region_sha256`.
  - `fingerprint.py`: Implemented `compute_fingerprint_v2` with stable 100 non-whitespace character window hash.
  - `severity.py`: Implemented `derive_severity` pure function with path-class caps and derivation tracking.
  - `suppression.py`: Implemented `ReviewSuppression`, `load_review_suppressions`, and diff-aware inline marker checking.
  - `admission.py`: Implemented single constructor `admit()` enforcing all admission gates and recording typed rejections.
- **Architectural & Pipeline Integration**:
  - `tests/test_architectural_invariants.py`: Added `test_finding_is_constructed_only_by_admission` ensuring no module outside `admit()` constructs `Finding`.
  - `src/devops_cli/ai/review/profile.py`: Added `rejections: dict[str, int]` tracking to `ReviewProfile` and `ReviewProfiler`.
  - `src/devops_cli/ai/review/pipeline.py`: Emitted `findings.sarif` from admitted findings; rendered introduced, pre-existing, and suppressed sections in `review.md`; reconciled `reported_findings` count with `findings.json`.
  - `src/devops_cli/security/sarif.py`: Preserved `tool_version`, `partialFingerprints`, and rule properties in SARIF roundtrips.
  - `src/devops_cli/security/bandit.py` & `semgrep.py`: Added `--ignore-nosec` and `--disable-nosem` flags to prevent scanners from silently hiding inline suppressed findings.
  - `.devops/review.toml`: Added path-class severity caps and B103 test-suite suppression with reason and expiry.

## Acceptance Criteria
- [x] A frozen `Finding` is built only by `review/admission.py::admit()`, verified by AST architectural invariant test (`test_finding_is_constructed_only_by_admission`).
- [x] Anchors: `ToolAnchor(run_id, result_index, rule_id)` and `AdvisoryAnchor(db, snapshot, advisory_id, purl, locked_version)` satisfy `Anchor` protocol (`test_anchor_protocol_and_implementations`).
- [x] Location check: paths verified in commit tree, line bounds enforced, `region_sha256` stored, logical locations verified against manifests/lockfiles, absolute paths normalized or rejected (`test_location_check_and_typed_rejections`).
- [x] Typed rejections counted in `profile.json`: `path-not-in-commit`, `line-out-of-range`, `object-not-in-commit`, `file-not-scanned`, `tool-not-run`, `canary-failed`, and `no-anchor`.
- [x] Fixture tree without `app/shell.py` rejects a result citing it (`test_location_check_and_typed_rejections`).
- [x] Severity is a pure function of SARIF level, rule severity, CVSS, and `.devops/review.toml` caps with derivation recorded (`test_severity_derivation_table`).
- [x] State transitions follow lifecycle invariants (`OPEN`, `SUPPRESSED`, `FIXED`, `CONFIRMED`) and valid confirmation rules (`test_state_transitions_and_invariants`).
- [x] Tools run with inline suppressions ignored (`--ignore-nosec`, `--disable-nosem`); markers added by change stay `OPEN` with `suppressed_by_change=True` (`test_suppressions_and_inline_markers`).
- [x] Test-path policy suppression from #1024 configured in `.devops/review.toml` covering B103 on test suites with reason and expiry.
- [x] Branch and PR reviews distinguish `introduced` vs `preexisting` based on base revision fingerprint presence (`test_introduced_vs_preexisting_branch_reviews`).
- [x] `findings.sarif` carries tool version, fingerprint v2, `partialFingerprints`, `rule_properties`, and never contains model output (`test_sarif_roundtrip_preserves_version_and_properties`).
- [x] `review.md` renders `## Introduced Findings`, `## Pre-existing Findings in Changed Files`, and `## Suppressed Findings` (`test_review_markdown_sections`).
- [x] `profile.json` and `findings.json` counts agree (`test_profile_and_findings_counts_agree`).
- [x] Two runs on fixture tree with equal input digests produce byte-identical `findings.json` and `findings.sarif` (`test_two_runs_fixture_tree_byte_identical`).
- [x] Offline tests with recorded tool outputs execute under 1 second without network or model calls.
- [x] Changelog fragment `changelog.d/871.md` added under `### Added`.
- Pending a person: On the S11 and loop inputs, verify every row names tool, version and rule, and 0 rows fall outside the tree.
