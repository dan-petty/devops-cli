# Proposal

## Why

Three rule documents name files that are gone or moved (#3508). An agent that follows them looks in the wrong place.

- `AGENTS.md` says that review guards are in `.devops/review.md`. #1916 retired that file. `.devops/review.toml` holds the suppressions and the severity caps.
- `docs/SELF_IMPROVEMENT.md` names `.devops/review.md` in a calibration record. The record is history and stays, but it does not say that the file is gone.
- `docs/TESTING.md` says that most test files sit flat in `tests/`. No test file sits at the top of `tests/`. The document also names 11 test files and one snapshot by the path that they had before they moved.

No test holds these facts. The link check of AGENTS.md reads link targets only, and `lychee` reads links, not backticked paths.

## What Changes

- `AGENTS.md`: the review row names `.devops/review.toml` for suppressions and severity caps, and not the retired guards file.
- `docs/SELF_IMPROVEMENT.md`: the calibration record of session `20260927-150737` says that #1916 retired `.devops/review.md`. The measurement protocol and the other records stay as they are.
- `docs/TESTING.md`: the layout text states that every test file sits in a mirror directory, and has no flat-file text. Each moved test file and the fail-to-pass snapshot have their real path.
- `tests/invariants/test_agents_md_claims.py`: `.devops/review.md` joins `CONST_DELETED_PROCESS_TERMS`. A new test fails when a backticked `tests/` path of `docs/TESTING.md` does not exist. It accepts a path with a `<placeholder>` and a path that a `*(target)*` mark follows.
- The change alters no command, option, message, manifest or service behavior. It edits documents and tests. So it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `AGENTS.md`, `docs/SELF_IMPROVEMENT.md`, `docs/TESTING.md`.
- Tests: `tests/invariants/test_agents_md_claims.py`.
- `devops ai agents` writes AGENTS.md from a template. The template does not hold the text, so it needs no change.

## Feasibility

- `ls .devops` on `origin/main` (dc9815e6) lists `review.toml`, `roadmap.toml`, `survey.toml` and `tuicr.config.toml`. There is no `review.md`. So the claim of AGENTS.md is false.
- `find tests -maxdepth 1 -name 'test_*.py'` prints nothing, and `find tests -mindepth 2 -name 'test_*.py'` finds 832 files. So the flat-file text is false.
- Before the fix, the new test reports 12 paths of `docs/TESTING.md` that do not exist. `find tests -name <file>` gives the real path of each one.
- `grep -rn 'review guards are in' src` finds nothing, so no generator template holds the AGENTS.md text.

## Existing Tool Considered

`lychee` runs in CI and reads links, not backticked paths, so it does not cover the need. `markdown-it-py` already parses the documents in `tests/invariants/test_agents_md_claims.py`. The new check uses its inline tokens and writes no regex over Markdown text. Cost: about 40,000 tokens to build, about 0 tokens to keep, and about 1 hour elapsed.
