# Proposal

## Why

Issue #1404. Intake plans candidates off the board before it places them. If a person adds an issue to the board and sets its fields during planning, `store.add_item` returns the person's card. Intake must not overwrite the values the person set. Today `_on_card` in `src/devops_cli/roadmap/intake.py` drops planned writes for fields the card already holds, but it does not log the skipped fields. Also, if a person sets a milestone on the issue before apply, intake must preserve that milestone and reflect it in the placement reason comment.

## What Changes

- Update `_on_card` in `src/devops_cli/roadmap/intake.py` to log a message naming the issue and the skipped fields whenever it drops planned writes.
- Update `_on_card` to read `item.milestone` and preserve the milestone if set on the card after planning.
- Add `intake_skipped_fields` to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`.
- Add offline `GitHubFake` tests in `tests/test_roadmap_intake.py` verifying:
  1. Intake drops all writes and logs skipped fields when a person sets Priority between plan and apply.
  2. Intake writes only missing fields and logs skipped Value when a person sets Value and a milestone with no Priority.
- The change sets `skip_specs: true` in `.openspec.yaml` because it adjusts internal intake placement logging and card reconciliation without altering public CLI options or spec requirements.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/intake.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/test_roadmap_intake.py`.

## Feasibility

- Premise confirmed against `src/devops_cli/roadmap/intake.py` (`_on_card` at line 1173) and `src/devops_cli/roadmap/github_store.py` (`add_item` at line 900).
- In unpatched code, `_on_card` drops fields present on the card but emits no log record.
- In unpatched code, `_on_card` only checked `decision.subject.milestone` and `item.restored`, ignoring milestones added to live cards before apply.
- Offline tests using `GitHubFake` confirm the store returns `AddedItem` with card fields and milestone intact.

## Existing Tool Considered

`logging.getLogger(__name__)` and `RoadmapMessages` provide the standard logging and messaging infrastructure.
`RoadmapStore` and `GitHubFake` provide the existing item lifecycle seams.
No new external tool is necessary.
