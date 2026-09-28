# Task 498: Finding Locations Keep Paths With `+`, `@`, `~` or `%`

**Issue**: [#498](https://github.com/dan-petty/devops-cli/issues/498)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

`canonicalize_finding_location` matches paths with `[a-zA-Z0-9_\-./\\]`. A path outside that class
falls through to a fallback that keeps its first path-like fragment. Every finding on files under
a corpus named `playbooks+core+...` (#415) was saved as `.data/reviews/corpora/playbooks`, with no
file and no lines.

### Key Deliverables Completed:

- [x] **One path character class**: the three location patterns (a path with lines, a
  `file:target` location, and a location embedded in prose) share `_PATH_CHARS`. It accepts
  letters and digits of any script and the punctuation file names use: `+` (`c++`,
  `playbooks+core`), `@` (`@scope`, `logo@2x`), `~` (`~/.config`) and `%` (`100%`).
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_location_paths.py`: for a path with each character and one with
    non-ASCII letters:
    - it survives alone, with a line and with a range;
    - reversed ranges, `#L` anchors, backticks and `, lines` are normalized as for any path;
    - it is extracted whole from prose;
    - a scoped package's `file:target` location is kept;
    - the #415 corpus finding keeps its file and lines through the `Finding` model.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
