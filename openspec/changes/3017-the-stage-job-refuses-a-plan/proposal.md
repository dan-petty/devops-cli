# Proposal

## Why

About 8 of 37 recent plans order their groups so that a group reads a path that only a later group creates (#3017). The stage job refuses such a plan, but its problem text names only the reading group, so the model cannot see which group to move. The issue asks that the problem name both groups.

## What Changes

- `path_problems` finds the first later group that lists a missing path in `creates` and names it in the problem.
- The problem text tells the model to move the creating group before the reading group.
- A new test in the shape of #2996 asserts that the problem names group 1 and group 2.
- A test asserts that a plan whose groups create what they read has no problem.
- The `roadmap-stage` spec delta states that the problem names both groups.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The plan names files that exist at the staged commit

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `openspec/changes/3017-stage-names-the-creating-group/proposal.md`, `openspec/changes/3017-stage-names-the-creating-group/design.md`, `openspec/changes/3017-stage-names-the-creating-group/tasks.md`, `openspec/changes/3017-stage-names-the-creating-group/specs/roadmap-stage/spec.md`
- Tests: `tests/roadmap/test_roadmap_stage_paths.py`

## Feasibility

- `search_code` for `path_problems` showed the check already exists in `src/devops_cli/roadmap/stage_paths.py:141` and is called from `check_proposal` in `src/devops_cli/roadmap/stage_change.py:298`, so the premise of the issue holds: the job refuses a forward-read plan.
- `read_file` of `src/devops_cli/roadmap/stage_paths.py:128-156` showed `_problem` takes only the reading group number, so the problem text names one group. The remaining work is to name the creating group.
- `read_file` of `tests/roadmap/test_roadmap_stage_paths.py:92-99` showed the existing test asserts only `group 1` in the problem, so it does not yet cover the acceptance criterion.
- `read_spec` of `roadmap-stage` showed the requirement `The plan names files that exist at the staged commit` holds the check, so the change modifies that requirement.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` runs the new tests, and `openspec validate --strict` checks the change folder.

## Existing Tool Considered

No open, maintained tool covers this project-specific validation of plan group ordering. The project keeps the check in its own `path_problems` function in `src/devops_cli/roadmap/stage_paths.py`, which #3010 already added. The written cost is one small pure function, two test cases and the maintenance of the message text; the cost is already paid, and this change adds one lookup and one message sentence.
