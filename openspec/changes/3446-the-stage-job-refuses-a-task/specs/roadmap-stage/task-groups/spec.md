## ADDED Requirements

### Requirement: A task path is listed by its own group
The stage proposal check SHALL refuse a path in a code span of a group's task text when the same group lists the path in neither `reads`, `changes` nor `creates`, unless the path sits under `openspec/changes/` or `openspec/specs/`, or the path is a folder of a path that the group lists in `creates`.

#### Scenario: Task names an existing file that the group omits
- **WHEN** A group names `tests/roadmap/test_roadmap_stage_eval_cases.py` in a code span of its task text, the staged tree holds that file, and the group lists it in no field.
- **THEN** `path_problems` returns one problem that names the group and the path.

#### Scenario: Task names a file that the group changes
- **WHEN** A group names `tests/roadmap/test_roadmap_stage_content.py` in a code span of its task text and lists the same path in `changes`.
- **THEN** `path_problems` returns no problem for that path.

#### Scenario: Task names a file that the group reads
- **WHEN** A group names `src/devops_cli/roadmap/stage_paths.py` in a code span of its task text and lists the same path in `reads`.
- **THEN** `path_problems` returns no problem for that path.

#### Scenario: Task names a change file and a living spec file
- **WHEN** A group names `openspec/changes/3446-the-stage-job-refuses-a-task-path/tasks.md` and `openspec/specs/roadmap-stage/spec.md` in code spans of its task text and lists neither path in a field.
- **THEN** `path_problems` returns no problem for either path.

#### Scenario: Task names the folder of a created test
- **WHEN** A group lists `tests/roadmap/test_new_case.py` in `creates` and names `tests/roadmap/` in a code span of its task text.
- **THEN** `path_problems` returns no problem for `tests/roadmap/`.

#### Scenario: Task names a missing file that the group omits
- **WHEN** A group names `tests/roadmap/test_absent.py` in a code span of its task text, the tree lacks that file, no group creates it, and the group lists it in no field.
- **THEN** `path_problems` returns the missing-path problem for that path, and no unlisted-path problem.

#### Scenario: The refusal comes from the message catalog
- **WHEN** A group names an unlisted path in a code span of its task text.
- **THEN** The problem is the `RoadmapMessages` text with the group number and the path filled in.
