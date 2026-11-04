# Design

## Decisions

- **Run the check from `content_problems` in `src/devops_cli/roadmap/stage_change.py`.**: `content_problems` already judges the text of a reply, and `check_proposal` calls it, so the stage job and the replay run one rule set with no git call.
- **Reuse the code-span path rule of `src/devops_cli/roadmap/stage_paths.py` for the What Changes items.**: One definition of a repository path keeps the group check and the What Changes check from drifting apart.
- **Accept a What Changes item that holds no repository path.**: An item may describe behaviour that a reader sees with no file named, and the issue keeps that item accepted.
- **Put the message in `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`.**: The project keeps every user-facing text of the roadmap in the message catalog, and the message names the unlisted path.
- **Add a case to the stage golden set as well as a unit case.**: The golden set exercises the replay gate that the issue names, so the new rule has a recorded baseline.

## Rejected alternatives

- **Add the check to `path_problems` in `src/devops_cli/roadmap/stage_paths.py`.**: `path_problems` judges the group paths against the files of the staged commit, so it needs git state and the replay cannot run it on a reply alone.
- **Add a new regular expression for a path in `src/devops_cli/roadmap/stage_change.py`.**: The group texts already read their paths with one code-span rule in `src/devops_cli/roadmap/stage_paths.py`, and a second grammar drifts from it.
- **Split each What Changes item on whitespace and treat each word as a path.**: An item names commands and prose, such as `uv run devops ci test`, so the split refuses valid plans.
- **Reuse `stage_problem_path` for the new message.**: That message speaks of a group, a staged commit and a place, not of a What Changes item and the lists of the groups.
- **Run the check from `render_change`.**: `render_change` writes the files of the change and runs in no replay gate, so a bad plan would reach the repository before a check reads it.
