# Task: An Inline Suppression Marker Hides Only Findings of the Tool It Belongs To (#1341)

**Issue**: [#1341](https://github.com/dan-petty/devops-cli/issues/1341)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/review

## Description
Admission (#871, fca29e9) honoured any inline marker on a finding's line, whichever scanner produced the finding: one pattern matched `noqa`, `nosec`, `nosemgrep` and `no-semgrep` alike. Before #1295 (f67f554), suppressed findings were still reported, so this stayed latent. Once suppressed findings left the report, a `# noqa: E501` on a line hid a Bandit or Semgrep security finding there.

Bandit itself ignores `# noqa`. Its own comment pattern (bandit 1.9.4, `core/manager.py` `NOSEC_COMMENT`) matches only `nosec`, and a probe with a real file confirms that a `# noqa: B602` line is still reported. A Copilot review thread on release pull request #1283 raised the bug.

## Key Changes
- **Markers per tool** (`src/devops_cli/config/constants.py`): `CONST_INLINE_SUPPRESSION_MARKERS` maps `bandit` to `nosec`, `semgrep` to `nosemgrep`/`no-semgrep`, and `ruff` to `noqa`. A tool that is not listed has no inline marker.
- **The check takes the tool** (`src/devops_cli/review/suppression.py`, `src/devops_cli/review/admission.py`):
  - `has_inline_marker` and `check_inline_marker_in_diff` take the finding's tool and match only its markers.
  - `_check_suppressions` passes `admit()`'s `tool` through.
  - The "added by this change" case follows the same rule, so another tool's marker added by the change does not mark the finding.
- **Tests** (`tests/test_review_admission.py`, `tests/test_review_security_tools.py`):
  - `test_an_inline_marker_suppresses_only_findings_of_its_own_tool` covers Bandit with `# noqa`, Semgrep with `# nosec` and Trivy with `# nosec`, which stay open, and each tool with its own marker, which is suppressed.
  - `test_a_marker_of_another_tool_added_by_the_change_does_not_mark_the_finding` covers the added-by-change case.
  - Four of these cases fail at bbc644b.
  - The pipeline test of a marker added by the change now uses Bandit's own `# nosec`.

## Acceptance Criteria
- [x] An inline marker suppresses only findings of the tool it belongs to, findings of a tool without its own marker are never suppressed inline, and the table lives in `config/constants.py`.
- [x] Tests show that a Bandit finding on a `# noqa` line and a Semgrep finding on a `# nosec` line stay open, and that each tool's own marker still suppresses, including the added-by-change case; the cross-tool cases fail at bbc644b.
- [x] The v0.2.28 section of `CHANGELOG.md` records the change in the #871 entry, in this pull request rather than through a fragment and a separate collation pull request. The owner decided on 2026-10-07 that the release's last fix lands as one pull request. `docs/ROADMAP.md` is not edited.
- [x] `uv run devops ci` passes.
