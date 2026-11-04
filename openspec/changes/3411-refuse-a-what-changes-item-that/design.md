# Design

## Decisions

- **Run the check from `check_proposal` in `src/devops_cli/roadmap/stage_change.py`.**: `check_proposal` holds the `StagedTree`, and the stage job and the replay both call it with that tree, so the check makes no git call.
- **Share the code-span path rule of `src/devops_cli/roadmap/stage_paths.py` for the What Changes items.**: A word is a repository path only by the suffixes and the top folders of the tree, so one function over the tree keeps the group check and the What Changes check from drifting apart.
- **Accept a What Changes item that holds no repository path.**: An item may describe behaviour that a reader sees with no file named, and the issue keeps that item accepted.
- **Accept a What Changes path under the living spec folder.**: `openspec archive` writes `openspec/specs/` and no group may, so the rule would refuse a valid plan that says the change gains a scenario. The plan of this change names that path in What Changes, so the check must leave it alone.
- **Put the message in `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`.**: The project keeps every user-facing text of the roadmap in the message catalog, and the message names the unlisted path.
- **Add a case to the stage golden set as well as a unit case.**: The golden set exercises the replay gate that the issue names, so the new rule has a recorded baseline. A new case changes the count in `tests/roadmap/test_roadmap_stage_eval_cases.py`, so that test changes with the case.

## Rejected alternatives

- **Add the check to `content_problems` in `src/devops_cli/roadmap/stage_change.py`.**: `content_problems` holds no tree, and a word is a repository path only by the suffixes and top folders of the tree. A tree-free rule would be a second path grammar, and the content gate would give a different answer from the job.
- **Add the check to `path_problems` in `src/devops_cli/roadmap/stage_paths.py`.**: `path_problems` judges the group paths in order against the files of the staged commit, and it has no place for the text of the proposal. The rule belongs beside the other checks of the reply in `check_proposal`.
- **Add a new regular expression for a path in `src/devops_cli/roadmap/stage_change.py`.**: The group texts already read their paths with one code-span rule in `src/devops_cli/roadmap/stage_paths.py`, and a second grammar drifts from it.
- **Split each What Changes item on whitespace and treat each word as a path.**: An item names commands and prose, such as `uv run devops ci test`, so the split refuses valid plans.
- **Reuse `stage_problem_path` for the new message.**: That message speaks of a group, a staged commit and a place, not of a What Changes item and the lists of the groups.
- **Run the check from `render_change`.**: `render_change` writes the files of the change and runs in no replay gate, so a bad plan would reach the repository before a check reads it.
