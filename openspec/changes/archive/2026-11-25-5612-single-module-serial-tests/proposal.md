# Proposal: #5612

## Why
A narrowed `devops ci test` run chooses serial versus parallel xdist workers from the count of collected tests (#4472). For a single test module just above 50 tests (such as `tests/roadmap/test_roadmap_claim.py` with 52 tests), starting a collection session and 4 xdist workers costs roughly 22 s versus 8.5 s when running serially (`-n 0`), making the single-module run over 2.5 times slower (#5612).

## What Changes
Make a narrowed `devops ci test` run given no `-n` and one target test module run serially (`-n 0`) without starting a pytest collection session, while keeping the collected-test count rule for two or more target modules and keeping explicit `-n` overrides.

- Update `_narrowed_workers` (`src/devops_cli/commands/ci.py`) to return `"0"` without calling `_collected_test_count` when `len(targets) == 1` (and update `docs/TESTING.md`, `HELP.ci.num_workers`, and regenerated docs via `devops docs generate`).
- Update `tests/commands/test_test_selection.py` and `tests/commands/test_ci_repeat.py` so existing multi-module collection tests pass two target modules, and add tests proving one target module runs with `-n 0` and zero collection spawns, two target modules collecting over 50 tests run parallel after collection, explicit `-n` overrides with no collection, and `--help` documents the single-module rule.

This changes observable CLI behavior (`devops ci test` worker selection and `--help` option description) and updates `ci-test-workers` requirements, so it carries a spec delta. Fits in one pull request.

## Capabilities
- `ci-test-workers` (`openspec/specs/ci-test-workers/spec.md`)

## Impact
- `src/devops_cli/commands/ci.py`: `_narrowed_workers`.
- `src/devops_cli/lang/en/help.py`: `num_workers`.
- `docs/TESTING.md`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`: regenerated/updated `-n` and narrowed-run rule descriptions.
- `tests/commands/test_test_selection.py`, `tests/commands/test_ci_repeat.py`: unit and offline process-double tests.

## Feasibility
Confirmed against `src/devops_cli/commands/ci.py:2151-2175`, `src/devops_cli/config/defaults.py:519-535`, `src/devops_cli/lang/en/help.py:1068-1072`, and `tests/commands/test_test_selection.py:620-885`: `_narrowed_workers` already resolves `targets` before starting `_collected_test_count`.

## Existing Tool Considered
None (alternatives verdict `none` recorded on #5612): `pytest-xdist` obeys explicit `-n` flags and does not choose serial vs parallel before collection without an external stored duration cache (already rejected in #4472). Cost to build and maintain inside `_narrowed_workers`: ~1 line of worker selection, help/doc updates, and offline selection tests (~4k tokens, <1 hour).
