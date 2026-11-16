# Proposal: #3995

## Why
The stage job measures the token consumption of a task group from the files that the group reads and the estimated created lines. It sets no limit on the number of files that a group changes. When a single task group changes many files across different subsystems, an implementation step can exhaust its token budget (for example, issue #3654 group 3 changed 7 files and hit its 8,000,000 token limit). Closes #3995.

## What Changes
- Add a new proposal gate `ProposalGate.GROUP_FILES = "group-files"` in `src/devops_cli/roadmap/stage/stage_change.py`.
- Add module constant `MAX_GROUP_CHANGES = 5` in `src/devops_cli/roadmap/stage/stage_change.py`.
- Add `is_prefix_move_group` in `src/devops_cli/roadmap/stage/stage_move.py` to identify exempt prefix move groups whose `changes` contains only the old modules of one prefix move and the modules that the group creates.
- Implement `group_files_problems` in `stage_change.py` and register it in `check_gates`.
- Add refusal message `stage_problem_group_files` to `src/devops_cli/lang/en/messages.py`.
- Update the staging prompts (`roadmap_stage_change.md`, `roadmap_stage_split.md`) to state the 5-file limit, the prefix-move exemption, and the split instruction.
- Update `docs/ROADMAP_WORKFLOW.md`, `docs/TELEMETRY.md`, and telemetry instrument descriptions.

## Capabilities
### roadmap-stage/task-groups
- Bounded file changes per task group (at most 5 files in `changes`), with exemption for prefix moves.

## Impact
- Prevents implement jobs from exceeding token budgets caused by wide multi-file task groups.
- No breaking changes for groups within limits or prefix moves.

## Feasibility
Confirmed against existing stage gate infrastructure: `ProposalGate`, `check_gates`, and `_moves` in `stage_move.py`.

## Existing Tool Considered
The alternatives check found no open tool or library for OpenSpec task group sizing. This change adds bounds checking in `stage_change.py`: 1,000 tokens to build, 100 tokens each quarter to maintain, and 15 minutes.
