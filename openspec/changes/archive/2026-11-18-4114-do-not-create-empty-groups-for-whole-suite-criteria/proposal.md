# Proposal

## Why

The stage planning prompt causes the model to create empty task groups for global acceptance criteria. When an issue contains whole-suite or non-functional criteria, such as suite duration bounds or offline execution requirements, the planner creates dedicated task groups solely to satisfy acceptance criteria mappings. These synthetic groups contain no substantive code changes, only edit module docstrings or repeat manual verification commands, waste execution steps in the implement runner, and trigger `group-no-files` plan check failures (#4114).

## What Changes

- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` instructs the model to map global, performance, or hermeticity criteria to the task group that delivers or completes the suite.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` forbids creating task groups that only update docstrings or restate instructions.
- The split prompt `src/devops_cli/ai/tasks/roadmap_stage_split.md` instructs the model to map global, performance, or hermeticity criteria to the task group that delivers or completes the suite, and forbids creating task groups that only update docstrings or restate instructions.
- The `roadmap-stage/task-groups` capability gains the requirement that forbids empty task groups and maps whole-suite criteria to the completing group.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/task-groups`: The stage prompts forbid empty task groups for whole-suite criteria

## Impact

- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds in the code at the staging commit: issues with whole-suite criteria currently produce empty task groups that fail `group-no-files` checks.
- Instructing the stage and split prompts prevents empty groups and guides criteria mapping to the group that completes the suite.
- The prompt rule test `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` verifies the prompt updates.
- The check is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- The second check is `uv run devops openspec check`.

## Existing Tool Considered

None. The stage prompts directly control model planning behavior in the roadmap pipeline. No external tool or library governs task group formation or criteria mapping in these task prompts.

## Dependencies

None.
