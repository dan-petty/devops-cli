# Design

## Decisions

- **Refuse the path in both `StageGroup` and `path_problems`.**: The model validator corrects the reply early, and the path gate also judges a recorded plan that `model_construct` built without the schema (`src/devops_cli/roadmap/stage_eval_gates.py`).
- **Refuse only `changes` and `creates`, and allow `reads`.**: `changes` and `creates` declare the files that the implementation step writes. A group may read a change document, and a task text or a `verify` command can name one.
- **Refuse the folder `openspec/changes` itself and every path under `openspec/changes/`.**: A prefix-only test would let a group change the folder itself. The constant `_CHANGES_DIRECTORY` already names the folder in `src/devops_cli/roadmap/stage_change.py`.
- **Add one message `stage_bad_change_path` that names the path and the rule.**: `stage_bad_path` says the path is not a repository path, which is false for a path under `openspec/changes/`.
- **Add the prompt rule as one bullet of the path rules.**: The planner reads the path rules as a list, and a separate bullet is easy for `tests/roadmap/test_roadmap_stage_prompt_rules.py` to assert.
- **Put the cases in the existing stage test modules, not in a new `tests/roadmap/test_stage_change.py`.**: `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_paths.py` and `tests/roadmap/test_roadmap_stage_prompt_rules.py` already hold the nearest cases and run in the same suite.
- **Write no task group that edits the change folder of this plan.**: The stage job renders the change folder from the reply, and the new rule forbids a group from writing under `openspec/changes/`. The spec delta comes from the `specs` key of the reply.

## Rejected alternatives

- **Check the rule in the `StageGroup` validator only.**: `src/devops_cli/roadmap/stage_eval_gates.py` builds a group with `StageGroup.model_construct` when the schema fails, so a recorded plan would skip the validator.
- **Check the rule in `path_problems` only.**: `src/devops_cli/roadmap/stage_paths.py` runs after the schema, so the model would get no correction before the job judges the plan.
- **Refuse the path in `creates` only.**: `src/devops_cli/roadmap/stage_change.py` holds `changes` as the list of files that a group writes, so a group can change an existing change file and create no path.
- **Refuse every path field, `reads` and the task texts included.**: `src/devops_cli/roadmap/stage_paths.py` reads task text only through code spans and cannot tell a read from a write, and the issue's own acceptance criteria require `reads` to stay allowed.
- **Reuse the message `stage_bad_path`.**: The message text of `_repository_path` in `src/devops_cli/roadmap/stage_change.py` says the path is not a repository path, which is false for a path under `openspec/changes/`.
- **Create a new test module `tests/roadmap/test_stage_change.py`.**: `probes` says `The path `tests/roadmap/test_stage_change.py` is no file of the staging commit.`, and `tests/roadmap/test_roadmap_stage_kind.py` and `tests/roadmap/test_roadmap_stage_paths.py` already test `StageGroup` and `path_problems`.
- **Add a task group that writes the change documents of this plan.**: The issue forbids exactly that, and the new validator would refuse the group: its `creates` path starts with `openspec/changes/`.
