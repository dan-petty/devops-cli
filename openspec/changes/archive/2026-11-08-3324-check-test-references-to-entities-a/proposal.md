# Proposal: #3324

## Why

When a plan removes or deprecates an exposed entity, tests and contract checks often reference that entity directly. The stage job does not check these references. Broken references cause immediate failures during implementation (#3324).

## What Changes

- Add `scan_removal_references` to scan `tests/` and `src/` for identifiers that `proposal.md` or `design.md` removes.
- Extract removed identifiers governed by removal verbs (`remove`, `delete`, `deprecate`, `drop`, `retire`), excluding container identifiers that follow prepositions such as `from`.
- Check if `tasks.md` names the referencing file. Unaccounted test references cause `devops roadmap stage` to exit non-zero and open no draft pull request.
- Report unaccounted source references in `src/` as warnings in the stage comment without failing the stage.
- Permit change folders that remove no entity to pass with no finding.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: removal-reference scan, removed names come from a removal verb, a task that names the file accounts for the reference, stage fails on an unhandled test reference, a source reference is a warning, a change with no removal passes

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_removal_references.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_removal_references.py`

## Feasibility

- The base commit contains the living spec `openspec/specs/roadmap-stage/spec.md`.
- Plan #3230 removed `valkey_set` while downstream tests in `tests/ai/mcp/` referenced it.
- Staging builds the change files in `_Planner._settle` and writes them in `_stage_one` of `src/devops_cli/roadmap/stage/stage.py`.
- Running `git grep` on `tests/` and `src/` finds symbols deterministically.

## Existing Tool Considered

`git grep` and `pytest` find broken references only after code changes are implemented. The planning stage currently lacks a reference scan for deleted entities. Cost to build: about 15,000 tokens and 1 hour.
