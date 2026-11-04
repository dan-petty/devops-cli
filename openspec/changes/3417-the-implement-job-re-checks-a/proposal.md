# Proposal

## Why

The implement job runs the task groups of a Staged plan without a deterministic check that the premise of the plan still holds, so a plan that adds a guard the base already runs (the plan of PR #3374 for #3368) duplicates the guard, or stops only when the step model notices (#3417).

## What Changes

- Extract the definition lookup of the stage probe into one shared function in the new module `src/devops_cli/roadmap/premise.py`.
- Call the shared function from `src/devops_cli/roadmap/stage_probe.py` so the stage job and the implement job share one definition check.
- Check the premise of each behavior group at the branch tip in `src/devops_cli/roadmap/implement_run.py`, before the group step runs.
- Return the item to New with the definition line when a behavior group task adds a guard that the branch tip defines, and run no step and write no file.
- Add the false-premise and true-premise tests to `tests/roadmap/test_roadmap_implement_job.py`.
- Record the new check on the implement page `docs/roadmap/implement.md`.
- Add the shared check and the behavior-group premise check as requirements of the capability `roadmap-implement-job`, so the delta holds the new behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job checks the premise of a behavior group at the branch tip, One shared function reports a definition at a commit

## Impact

- Code: `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/implement_run.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_premise.py`, `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

- The probes say of the cited implement module: "The path `src/devops_cli/roadmap/implement_run.py` is a file of the staging commit."
- The probes say of the cited test module: "The path `tests/roadmap/test_roadmap_implement_job.py` is a file of the staging commit."
- The probes say of the stage probe: "The path `src/devops_cli/roadmap/stage_probe.py` is a file of the staging commit."
- The probes say of the shared module that this change adds: "The path `src/devops_cli/roadmap/premise.py` is no file of the staging commit. No commit in the history deleted or renamed it." So the module is a path to create, and the premise of the issue holds.
- read_file `src/devops_cli/roadmap/stage_probe.py` showed the definition lookup that the change extracts: `_definition_pattern` builds the expression and `_Run.identifier` runs `git grep -n -E` with it at the staging commit.
- read_file `src/devops_cli/roadmap/implement_run.py` showed the group loop and `_return_premise`, which runs only after the step model reports a premise request, so no deterministic check runs before a group today.
- read_file `src/devops_cli/roadmap/step_files.py` showed that a parsed group carries its kind, so the check can run for a behavior group only.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/test_roadmap_stage_probe.py`, then `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`, then `uv run devops ci docs`.

## Existing Tool Considered

The stage premise check of #3176 in `src/devops_cli/roadmap/stage_probe.py` covers this need: it reports whether a commit defines a cited identifier. The change extracts its definition lookup into `src/devops_cli/roadmap/premise.py` and reuses it, instead of building a second check. Cost: about 6,000 tokens to extract and test, about 1,000 tokens to keep, and about 2 hours elapsed. The change deletes no internal code.

## Dependencies

None.
