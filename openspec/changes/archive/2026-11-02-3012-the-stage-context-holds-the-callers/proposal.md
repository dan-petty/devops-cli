# Proposal

## Why

Issue #3012: 17 of 37 plans ignore code, tests or specs that exist. The stage job and the refine job share `collect_context` (`src/devops_cli/roadmap/refine.py`). It gives the model the cited files, at most 5 identifier greps of 5 lines each (20 lines in all), and a tree of at most 50 files. It never searches `tests/`, and it never says which requirements a spec already holds. So a plan adds a failure path beside `CheckFailure`, duplicates `ToolRun.config_digest`, or breaks a test that pins an argv.

## What Changes

- For each identifier that the item cites in backticks (at most 5), `collect_context` adds a section that lists the Python files naming it: test files first, then callers. The list holds at most `CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL` (50) paths, and says how many it left out. The 20-line cap of the existing "Identifier matches" section stays: the new bound is on paths, because `git grep -l` prints one path per line.
- For each base spec that covers a cited file (at most 5 specs, at most 40 names each), `collect_context` adds the names of its `### Requirement:` headings. A spec covers a file by the name of its module, or when its text names the path.
- Both kinds of section come before the cited code, so the cut of the token budget keeps them.
- The change adds three constants to `config/constants.py`, and no setting, command, option or message. The stage job and the refine job read the new context with no change of their own.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: ADDED requirements for the content and the bound of the context that `collect_context` builds. No existing requirement of `openspec/specs/roadmap-refine/spec.md` or `openspec/specs/roadmap-stage/spec.md` speaks of the context, so nothing is MODIFIED.

## Impact

- Code: `src/devops_cli/roadmap/refine.py` (new helpers and two lines in `collect_context`), `src/devops_cli/config/constants.py` (three constants).
- Tests: `tests/roadmap/test_roadmap_refine.py` (the git fake answers `git grep -l`, and six new tests). The issue names `tests/roadmap/test_refine.py`; the file is `test_roadmap_refine.py`.
- Existing code to keep passing: `collect_context` and its two callers, `StagePlanner._request` in `src/devops_cli/roadmap/stage.py` and the refine round in `refine.py`.
- Token cost: about 1,200 tokens on the issue itself and at most about 5,000 in the worst case. See `design.md`.

## Feasibility

Each fact below comes from a run on `origin/main` at `ac16675a`, with git 2.43.0, on 2026-11-02.

- How the context is built today. `collect_context` (`src/devops_cli/roadmap/refine.py`) reads `CONTEXT.md`, up to 5 files of `docs/adr`, up to 10 cited files, up to 5 identifier greps, and a tree. `_collect_cited_files` stops at 10 files. `_collect_identifiers` runs `git grep -n -F -w -e <ident> <sha> --` for the first 5 identifiers in sorted order, keeps 5 lines of each and 20 in all. The pathspec is empty, so `tests/` is searched, but the 20 lines go to the first files in path order and the files of `tests/` come last. The issue's claim that the context does not search `tests/` is true in effect, not by pathspec.
- The two callers. `StagePlanner._request` (`src/devops_cli/roadmap/stage.py`) calls `collect_context(..., max_tokens=window // 2)` (`_WINDOW_SHARE_CONTEXT`). The refine round (`refine.py`) calls it with the context window of the `analysis` task, or 8,192 when none is set.
- The command works. On this checkout, `git grep -l -z -F -w -e run_subprocess <sha> -- '*.py'` prints `<sha>:<path>` ended by NUL, and `*.py` matches at every depth.
- The issue's premise that "a file maps to a capability by the mapping the project already uses for spec deltas" is false. No code maps a file to a capability. A delta is keyed by the capability name that the planner picks (`stage_change.py` writes `specs/<capability>/spec.md`), and `stage_validate.py` copies the base spec of that name. `capabilities_of` (`stage.py`) lists only the names under `openspec/specs/`. No spec records the files it covers: `git grep -lE "src/devops_cli/[a-z_/]+\.py" -- openspec/specs` lists 4 of 162 specs.
- So this change defines the mapping, and keeps it to two checks that need no stored data: the name of the spec against `<package>-<module>` of the file, and the text of the spec naming the path. The first check covers 40 of the 653 modules of `src/devops_cli` (6 %) by name alone, for example `roadmap/refine.py` to `roadmap-refine`, and `roadmap/stage_eval_run.py` to `roadmap-stage-eval` and `roadmap-stage`. The second check covers the 4 specs that name a path. The coverage is small. A spec for the other modules would need a recorded list of files per spec, which is a larger change; see Workflow follow-up in `tasks.md`.
- Nothing newer covers the need. `git grep -ln "Tests and callers" -- src openspec` on the base prints nothing.

## Existing Tool Considered

`git grep -l` is the open tool, and the change uses it: it already lists the files, one path per line, in a fixed order. No open library builds a bounded prompt context from such a list. The need is the filter by test pattern, the bound, the note of the cut, and the read of requirement names from a spec. That part is project code (about 110 lines in `refine.py`, about 130 lines of tests).

Written cost, estimated: about 60,000 tokens to build with the tests, about 3,000 tokens a year to keep the patterns and bounds in step with the layout, about 10,000 tokens to fix a miss, and about two hours of elapsed time. The measure of the context is in `design.md`.

The change deletes no internal code. It replaces no function: `_collect_identifiers` stays, because its lines show how a symbol is used, which a list of paths does not.
