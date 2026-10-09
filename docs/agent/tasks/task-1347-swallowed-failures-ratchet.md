# Task: Swallowed Failures Ratchet (#1347)

**Issue**: [#1347](https://github.com/dan-petty/devops-cli/issues/1347)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: priority/p1-high
**Scope**: type/test, scope/cli, priority/p1-high
**Feasibility**: Verified ruff JSON output for BLE001, S110, S112 and AST check for unread check=False process calls against real src/ tree.

## Description
Implements a ratchet invariant test preventing swallowed failure sites (`BLE001`, `S110`, `S112`, and unread `check=False` process calls) under `src/` from growing unnoticed. Per-file ceilings are recorded in `tests/fixtures/swallowed_failures_ceilings.json`. When a file exceeds its ceiling, the test fails naming each site (`file:line: rule`). When a file's count falls below its ceiling, the test fails with instructions and the exact command to lower the ceiling (`uv run python tests/test_swallowed_failures_ratchet.py --lower`), locking in the gain.

## Acceptance Criteria
- [x] A ratchet invariant counts, per file under `src/`:
  - `BLE001`, `S110` and `S112` sites, using ruff's own rules (`ruff check --select ... --output-format json`), not a hand-written parser;
  - calls passing `check=False` whose result is never read: no `.returncode`, `.stdout` or `.stderr` use, and the result is not returned. This one uses an AST check.
- [x] The ceilings are today's counts. A file over its ceiling fails with file:line and the rule. A file under its ceiling fails with the command that lowers it, so every fix also locks the gain in.
- [x] Tests cover a new blind except, a new `except: pass`, an unread `check=False` and a lowered ceiling.
- [x] `changelog.d/<n>.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.

## Deliverables
- [x] Added `CONST_SWALLOWED_FAILURES_RUFF_RULES` and `CONST_SWALLOWED_FAILURES_CHECK_ATTRS` to `src/devops_cli/config/constants.py`.
- [x] Recorded baseline ceilings per file under `src/` in `tests/fixtures/swallowed_failures_ceilings.json`.
- [x] Created `tests/test_swallowed_failures_ratchet.py` implementing the ratchet invariant, AST analysis of unread `check=False` calls, `--lower` command handler, and comprehensive tests.
- [x] Added changelog fragment `changelog.d/1347.md`.
