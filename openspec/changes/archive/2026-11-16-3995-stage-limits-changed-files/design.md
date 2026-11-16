# Design

## Decisions
- **Limit value**: `MAX_GROUP_CHANGES = 5` as a module constant in `stage_change.py`.
- **Gate name**: `ProposalGate.GROUP_FILES = "group-files"` registered in `check_gates`.
- **Prefix move exemption**: A group is exempt if it moves exactly one prefix, its `changes` holds only old modules of that prefix and created modules, and all created modules are relative to the new subpackage directory.
- **Refusal message**: Names the group number, group title, and count of changed paths (`stage_problem_group_files`).
- **Prompt and docs**: State the 5-file limit, the prefix-move exemption, and the split instruction in `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `roadmap_stage_split.md`, and `docs/ROADMAP_WORKFLOW.md`.

## Rejected alternatives
- 4 files limit: Refuses valid accepted plans with a 5-path `other` group.
- 10 files limit: Allows 7-file groups that cause implement token exhaustion.
- Counting all paths in prefix moves: Refuses valid prefix moves that rename 5 modules (10 paths).
- Exempting any move group: Allows unrelated files to bypass the limit.
- Dynamic setting instead of constant: Plan-check rules are deterministic constants.
