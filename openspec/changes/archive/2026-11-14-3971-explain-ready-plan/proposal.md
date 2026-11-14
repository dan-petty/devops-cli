# Proposal

## Why

When `stage_ready` marks a plan pull request ready, `devops roadmap explain` says "Its pull request #<number> is not an open draft." The message suggests a fault, but the plan waits for a person to review and merge it (#3971).

## What Changes

- `_pull_reason` names an open plan pull request that is no longer a draft as ready for review and awaiting merge.
- A closed or merged pull request, and an implement pull request that left draft status, keep the old message.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/selection`: The reason for an open plan pull request that is ready for review names the merge wait.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_selection.py`

## Feasibility

- The item record already holds `stage.pr`, and `PullStatus` holds the title and state.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

No outside tool applies. The change adds one message and one condition.
