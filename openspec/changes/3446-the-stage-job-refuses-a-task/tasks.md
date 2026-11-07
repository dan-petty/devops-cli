# Tasks

## 1. Refuse a task path that the group lists nowhere

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`, `openspec/specs/roadmap-stage/spec.md`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_content.py`, write a case that stages a proposal whose group names `tests/roadmap/test_roadmap_stage_eval_cases.py` in a task code span while the group lists it in no field, and asserts that `path_problems` returns one problem that names the group and the path. Add cases for a listed path, a path under `openspec/changes/` and `openspec/specs/`, a folder of a created path, and a missing unlisted path that keeps the missing-path problem
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage_paths.py`, add `_SPECS_DIRECTORY: Final[str] = "openspec/specs"` and a helper that says whether a path sits under the change folder or the living spec folder. In `path_problems`, build the set of paths that the group lists, with `_folders_of` over its `creates`. For a path of `_Place.TASK` that the tree holds or that an earlier group creates, report the new message when the path is in neither set and sits under neither write folder. Add the field to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`, with the group and the path as its placeholders, and report it through `_problem`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## Criteria

- Group 1: The stage proposal check SHALL refuse a path in a group's task code span when the group lists the path in neither `reads`, `changes` nor `creates`.
- Group 1: The check SHALL accept a path in a group's task code span when the same group lists the path in `reads`, `changes` or `creates`.
- Group 1: The check SHALL accept a task code-span path under `openspec/changes/` or `openspec/specs/` even when the group lists the path in no group field.
- Group 1: The check SHALL accept a task code-span folder when the same group lists a path under that folder in `creates`.
- Group 1: The new refusal SHALL use a message field in `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`.
- Group 1: The check SHALL use the staged tree that `check_proposal` holds and SHALL make no git call.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
