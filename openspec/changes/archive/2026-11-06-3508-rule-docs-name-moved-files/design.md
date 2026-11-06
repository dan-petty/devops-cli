# Design

## Context

See proposal.md for the cause (#3508). Three documents name paths that moved or were deleted. No check reads a backticked path in a document.

## Goals / Non-Goals

**Goals:**
- Make the three documents true.
- Fail a test when `docs/TESTING.md` names a `tests/` path that does not exist.

**Non-Goals:**
- Edit lines 867 to 989 of `docs/SELF_IMPROVEMENT.md`, `CHANGELOG.md`, `openspec/specs/review-conventions/spec.md` or an archived change.
- Check every backticked path of every document.

## Decisions

### 1. The calibration record stays and names the retirement

- **Decision**: Keep the line and add a note that #1916 retired the file, and that `.devops/review.toml` now holds suppressions and severity caps.
- **Alternative considered**: Rewrite the line to name `.devops/review.toml`.
  - *Rejected*: That file holds suppressions and caps, not the settled claims that the record names. A rewrite would make the history false.

### 2. The check reads inline code tokens

- **Decision**: Parse `docs/TESTING.md` with `markdown-it-py`, take each `code_inline` token that is a `tests/` path, and test that it exists. A path with a `<placeholder>` is checked up to the placeholder. A path that an emphasis starting with `(target` follows is skipped.
- **Alternative considered**: Skip each path that does not exist.
  - *Rejected*: The check would miss the moved paths that this change corrects.
