# Proposal

## Why

ADR 0007 asks a test to reach private code through the public interface and to double only process edges. The ban held `tests/commands/` and `tests/invariants/`, so the rest of `tests/` could add a string patch of a `devops_cli` name or a private import with no signal. `docs/TESTING.md` also named the narrower ban (#5248).

## What Changes

- Add `_INTERNAL_PATCH_CEILING` (377) and `_PRIVATE_IMPORT_CEILING` (432) to `tests/invariants/test_source_tree.py`, in tests over all of `tests/` that only fall.
- Correct the two sentences of `docs/TESTING.md` that named only the narrower ban.

## Capabilities

### New Capabilities

- `test-ratchets`: the ceilings of the retired test forms.

### Modified Capabilities

None.

## Impact

- Tests: `tests/invariants/test_source_tree.py`
- Document: `docs/TESTING.md`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/../tests/invariants/test_source_tree.py:582:def find_devops_cli_string_patches(` and `:645:def find_private_devops_cli_imports(` scan a directory.
- The tree holds 377 string patches and 432 private imports on that day; the numbers came from both functions.
- `uv run pytest tests/invariants/test_source_tree.py` passes after the change.

## Existing Tool Considered

The two scanners are in the file. The change adds two constants and two tests: about 300 tokens to build and 50 a quarter to keep.

## Dependencies

None.
