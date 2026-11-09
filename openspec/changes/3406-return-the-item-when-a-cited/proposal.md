# Proposal

## Why

The premise probe of the stage job asks the staging commit about each path and identifier that an
issue cites. It reads a class field reference such as `PullStatus.labels` as a path, and no file
holds that path, so the probe says that the path is no file of the staging commit. Issue #3344
cited `PullStatus` without `labels`, but commit `499a5462` (#3399) had already added the field. The
stage job still staged the plan of pull request #3350 and its `## Feasibility` said that the field
is absent. A plan can therefore spend a full stage run on a gap that a merged commit has closed
(#3406).

## What Changes

- Add a class field reference to the premise probe. When the issue body cites `Class.field` and
  the staging commit defines `Class`, the probe reads the class and reports the file and line of
  the field, or says that the class defines no field of that name. The reference is no longer
  reported as a path.
- Detect a line of the body that states that a class field is absent, either as `Class.field` or as
  `Class` and `field` around an absence phrase such as `defines no` or `lacks`.
- Return the item to New with the probe line as evidence when the body states that a cited field is
  absent and the staging commit defines it. The job makes no model call for the item and records
  `refine.next_step` as `edit`, so a body edit brings the item back to refine.
- Reuse the AST reader of `src/devops_cli/roadmap/stage/stage_models.py` (#3344). The git commands
  stay in the probe, so each one counts against
  `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A cited class field is probed at the staging commit, and a false absence returns
  the item.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_probe.py`,
  `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/stage/stage.py`,
  `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_probe.py`,
  `tests/roadmap/stage/test_roadmap_stage_job.py`

## Feasibility

- `uv run python` calls `probe_premise` on the current commit with the body "The issue says
  `PullStatus.labels` is absent.". The probe prints "The path `PullStatus.labels` is no file of the
  staging commit. No commit in the history deleted or renamed it." and `missing` holds
  `PullStatus.labels`. This is the defect that #3406 names.
- The current `src/devops_cli/github/client.py` defines `labels` at line 88 of `PullStatus`, so the
  premise of #3344 is false at the current commit.
- `src/devops_cli/roadmap/stage/stage_models.py` already parses a module with the standard library
  `ast` (#3344). The change adds a reader of the field lines of each class in that module and no
  dependency.
- The stage job returns an item to New for a false premise today only through the model, and the
  probe writes only lines. `src/devops_cli/roadmap/stage/stage.py` has the write paths
  `_return_blocked` and `_stop_on_budget`, so the return reuses the same job record writes.

## Existing Tool Considered

No open, maintained tool reads a class field at a git commit. `mkdocstrings/griffe` was checked on
2026-11-06 and covers a docstring or a signature, not a field of a named class at a commit. The
change extends the premise probe with the standard library `ast` and the `git` calls that the probe
already runs, so it adds no dependency. Cost: about 10,000 output tokens to build and test, about
1,500 tokens for each later fix, and about 3 hours elapsed.
