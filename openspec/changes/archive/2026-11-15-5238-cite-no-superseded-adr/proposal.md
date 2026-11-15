# Proposal

## Why

ADR 0003, ADR 0011 and ADR 0012 are superseded, and code, tests and workflows still cited them. A citation of ADR 0003 was false since ADR 0016, and the citations of ADR 0012 named a release process that ADR 0013 replaced (#5238).

## What Changes

- Add `tests/invariants/test_adr_superseded_citations.py`: it reads the status from the front matter of each `docs/adr/*.md`, scans `src/`, `tests/` and `.github/` for `ADR <number>`, and fails on a number whose record is superseded. Archived change folders, `CHANGELOG.md` and `docs/adr/` are history and stay out.
- Move the citations of ADR 0003 to ADR 0017 or ADR 0021, and the citations of ADR 0012 to AGENTS.md rule 1, ADR 0004 or ADR 0021.
- Move the citations of ADR 0002 to ADR 0016, its successor for the job record and the rule against reverting a person's change.

## Capabilities

### New Capabilities

- `adr-records`: the citation rule of the ADR process.

### Modified Capabilities

None.

## Impact

- Tests: `tests/invariants/test_adr_superseded_citations.py`
- Sources and tests: the citation lines under `src/`, `tests/` and `.github/`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/roadmap/adr.py:181:def adr_of(` reads the front matter, and `AdrStatus.SUPERSEDED` names the retired records.
- The front matter of ADR 0003, 0011 and 0012 holds `status: superseded` and its successor.
- `tests/support/paths.py` gives `REPO_ROOT`, and the invariant tests already read the tree.
- `uv run pytest tests/invariants/test_adr_superseded_citations.py tests/roadmap` passes after the change.

## Existing Tool Considered

The repository already holds the front-matter reader. A text scan over three folders is 40 lines: about 1,500 tokens to build and 100 a quarter to keep.

## Dependencies

#5237 is open; the front-matter reader that this test needs is already on `main`.
