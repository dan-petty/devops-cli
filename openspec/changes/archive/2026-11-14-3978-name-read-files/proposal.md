# Proposal

## Why

The stage prompt tells the model to write every path in a code span, but it does not say that each group that changes files must name an existing file. `named_files` packs only the existing files that the task text names, so a group that names only new files packs no file and its step starts with weak context (#3978).

## What Changes

- `src/devops_cli/ai/tasks/roadmap_stage_change.md` requires each group that changes files to name at least one existing repository file in a code span, and states that `named_files` packs those files.
- A prompt-rule test holds the rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `named_files` in `src/devops_cli/roadmap/step_files.py` already reads the code spans of the task text and keeps the existing files.
- Verification command: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

## Existing Tool Considered

No tool covers a prompt instruction. `named_files` already packs the files the text names.
