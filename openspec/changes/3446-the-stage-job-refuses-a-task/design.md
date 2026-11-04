# Design

## Decisions

- **Extend `path_problems` in `src/devops_cli/roadmap/stage_paths.py` with the new rule.**: The function already walks each place of a group and receives the `StagedTree`, so it holds the group's own lists and the tree in one loop.
- **Read task paths with the existing `code_spans` and `tree.paths_in` rule.**: The project keeps one code-span path grammar in `src/devops_cli/roadmap/step_files.py`, and the implement step reads the same spans.
- **Accept a task path under `openspec/changes/` and `openspec/specs/` with no listing.**: The stage job writes the change folder and `openspec archive` writes the living spec, so no group lists those paths.
- **Accept a task folder that holds a path of the same group's `creates`.**: A task names `tests/roadmap/` while the group lists the file under it, and the implement step packs that file.
- **Report the unlisted refusal only for a path that the tree holds or that an earlier group creates.**: A path that the tree lacks keeps the existing missing-path sentence, so one path gets one problem with the cause that a person fixes first.
- **Add a field to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` and report it through `_problem`.**: The project keeps user-facing text in the catalog, and the sentence names the group and the path as the other path problems do.
- **Read the held `StagedTree` and make no git call.**: `check_proposal` already holds the tree at the staged commit, and a second read of the tree would repeat work that the caller did.

## Rejected alternatives

- **Add a separate loop in `check_proposal` in `src/devops_cli/roadmap/stage_change.py`.**: `check_proposal` calls `path_problems`, and a second loop would repeat the code-span reading and the problem formatting of `_named` and `_problem` in `src/devops_cli/roadmap/stage_paths.py`.
- **Write a second parser for the paths of a task text.**: `step_files.code_spans` is the one code-span rule, and the module docstring of `src/devops_cli/roadmap/stage_paths.py` says that only the code spans of a task count because the implement step reads those and no other text.
- **Accept a path that any group lists.**: A later group does not pack the file for this step, so the Impact of the naming group would still omit it.
- **Run `git ls-files` inside the check to test a listed path.**: `check_proposal` passes a `StagedTree` that the caller read with one `git ls-files`, and `StagedTree.read` is the only place that runs it.
- **Put the refusal text inline in `src/devops_cli/roadmap/stage_paths.py`.**: Every other sentence of the module comes from `MESSAGES.roadmap`, and `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` holds them.
