# Proposal

## Why

The plan of #3409 held a group whose only task was to fix a roadmap test if a new rule broke it. No test changed, so the implement step found no work and stopped the item with implement_stop_no_change (#3433).

## What Changes

- The stage change module refuses an other group whose every changed path is under tests and whose implementation names no test function in a code span.
- The planner prompt states that a group gives one exact change and names the failing test that it updates.
- The messages table holds the refusal sentence, which names the title of the group.
- New cases in the stage content test prove the refusal, the accepted group, the group with a source path and the sentence that names the group.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A test-only other group names its test function

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`

## Feasibility

- The probe confirms the cited stage module: The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.
- The probe confirms the cited test: The path `tests/roadmap/test_roadmap_stage_content.py` is a file of the staging commit.
- The probe confirms the cited prompt: The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.
- The probe confirms the cited implement step: The path `src/devops_cli/roadmap/implement_step.py` is a file of the staging commit, and the context shows `_stage` is called only there.
- The context code of the stage module shows `content_problems(proposal, probes)` and `check_proposal` calling it, and the caller map lists `src/devops_cli/roadmap/stage_eval_gates.py` beside it, so one rule reaches the stage job and the replay.
- The context lists `tests/roadmap/test_roadmap_stage_content.py` as the only test of `content_problems`, so the new cases run offline with no model, no cluster and no network.
- The first checks of the implementation are `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py`, then `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool reads a plan task for a conditional. The stage check already reads the task texts, so the rule extends `content_problems`. The cost is about 3,000 tokens to build, about 1,000 tokens to keep and fix, and about 2 hours.

## Dependencies

None.
