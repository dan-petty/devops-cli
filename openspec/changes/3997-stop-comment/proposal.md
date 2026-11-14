# Proposal

## Why

A run that stops after `_push_passed` has put the commits of the passed groups on the branch of the pull request. `stop()` writes the pull request comment only when the run applied an amendment, so a reviewer sees a failed `Plan Check` on the pushed commits and no explanation of the stop (#3997).

## What Changes

- `stop()` writes the stop text to the pull request of the run whenever `self.pull` is set, after the push.
- The one comment of the run holds the stop text, the step table, the amendments, the scoped runs and the notes. A second stop of the same run updates it in place through the existing marker and run id.
- A stop with no pull request writes only the issue comment.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/stops`: A stop with a pull request writes the status comment there.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- `_comment` already posts or updates the one comment of the run with the marker and run id.
- `stop()` already builds the stop text for the issue.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The GitHub session already posts and updates the comments through gidgethub (ADR 0006). The change reuses `_comment` and adds no library.
