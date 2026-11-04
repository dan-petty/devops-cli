# Proposal

## Why

`path_problems` in `src/devops_cli/roadmap/stage_paths.py` checks each path of a plan against the files of the staged commit and the `creates` of the groups. It never checks that a path named in a task code span is one that the same group lists, so a group can name a real file that it does not list. The plan then renders an Impact without the file and packs no file for the implement step, while every gate passes (#3446).

## What Changes

- `path_problems` in `src/devops_cli/roadmap/stage_paths.py` refuses a task code-span path that its group lists in neither `reads`, `changes` nor `creates`.
- A task path under `openspec/changes/` or `openspec/specs/` stays accepted, because the stage job and `openspec archive` write those folders.
- A task path that is a folder of a path in the group's `creates` stays accepted.
- A message field of `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` carries the refusal, with the group number and the path.
- `tests/roadmap/test_roadmap_stage_content.py` holds a case for the refusal and a case for each accepted form.
- The `roadmap-stage` capability gains one requirement for the new refusal, because the stage job reports a new problem to a person.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A task path is listed by its own group

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`

## Feasibility

- The premise holds in the code of `src/devops_cli/roadmap/stage_paths.py` at the staging commit. `_named` yields each task code-span path as `_Place.TASK`, and `path_problems` then tests existence only: `if path in reported or path in created or exists: continue`. No branch compares a task path with `group.reads`, `group.changes` or `group.creates`, so a listed path and an unlisted path take the same route.
- The probes confirm that the two cited modules are files of the staging commit: "The path `src/devops_cli/roadmap/stage_paths.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit."
- The probes confirm the message catalog and the test module that the issue changes: "The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_stage_content.py` is a file of the staging commit."
- The probes confirm the living spec and the two test modules that the issue cites as the case of PR #3436: "The path `openspec/specs/roadmap-stage/spec.md` is a file of the staging commit.", "The path `tests/roadmap/test_roadmap_stage_eval_run.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_stage_eval_cases.py` is a file of the staging commit."
- The probes confirm that the change folder is no file of the commit and that no commit removed it: "The path `openspec/changes/3446-the-stage-job-refuses-a-task-path/tasks.md` is no file at the root of the staging commit." and "No commit in the history deleted or renamed it." The stage job writes that folder, so the rule accepts a task path under it and this plan creates none.
- The docstring of `src/devops_cli/roadmap/stage_paths.py` names the four places of a group: `reads`, `changes`, the code spans of its three tasks, and the words of `verify`. The same file holds `_folders_of` and `_first_creators`, which already build the folders above a created path, so the folder rule reuses a function that exists.
- The first check of the implementation against the real system is `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py`, which runs the new cases beside the existing content cases.
- The second check is `uv run devops openspec check`, which validates the added requirement and its scenarios.

## Existing Tool Considered

No open, maintained tool or library covers the check of a plan against the files of a commit; the check reads this repository's own `StageProposal` schema. The change extends the existing `code_spans` and `StagedTree.paths_in` rule in `src/devops_cli/roadmap/stage_paths.py` and builds no parser. It deletes no code. The written cost is about 2k tokens to build, keep and fix, and 30 minutes.

## Dependencies

None.
