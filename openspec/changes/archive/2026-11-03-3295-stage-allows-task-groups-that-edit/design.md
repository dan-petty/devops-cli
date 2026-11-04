# Design

## Decisions

- **Reject an `openspec/specs/` path in a `StageGroup` model validator, not in `check_proposal`.**: `StageGroup` is the schema of every task group, so the rule covers the proposal reply, the split reply and a direct validation. The schema also sends the message back to the model.
- **Check `changes` and `creates` only, and leave `reads` open.**: `changes` and `creates` list the files that a step writes. A step may read a living spec as context, and the issue asks to stop edits only.
- **Reject the prefix `openspec/specs/` alone.**: The prefix names the living specs. Issue #3285 governs `openspec/changes/`, while this change governs living specs under `openspec/specs/`.
- **Raise `ValueError` with a message that names the path and says that only `openspec archive` writes living specs.**: This matches `_creates_are_changes`, and the model needs the offending path to correct its reply.
- **Put the path cases in `tests/roadmap/test_roadmap_stage_paths.py` and the prompt case in `tests/roadmap/test_roadmap_stage_prompt_rules.py`.**: The modules already hold the `StageGroup` path rules and the prompt rules, so no second module covers the same rule.

## Rejected alternatives

- **Check the prefix in `check_proposal` only.**: `check_proposal` in `src/devops_cli/roadmap/stage_eval_gates.py` runs after schema validation and does not see the split reply, so a `StageSplit` group would pass.
- **Reject every `openspec/` path in this change.**: Issue #3285 governs `openspec/changes/`, while this change governs living specs under `openspec/specs/`.
- **Reject an `openspec/specs/` path in `reads` too.**: `reads` lists context that a step opens, and the issue asks to stop edits; the refine block of the issue states that a step may read a living spec.
- **Create `tests/roadmap/test_stage_change.py` as the issue's Proposed Solution says.**: `probes` reports "The path `tests/roadmap/test_stage_change.py` is no file of the staging commit.", and `tests/roadmap/test_roadmap_stage_paths.py` already tests `StageGroup` path rules.
