# Proposal

## Why

Issue #2319: GitHub refuses to add 149 issues to project board 2, and 46 of them are open, so `devops roadmap run` cannot place them.

- The GraphQL add (`addProjectV2ItemById`) fails with `INTERNAL`. The REST add (`POST /users/<owner>/projectsV2/<board>/items`) fails with `422 Content already exists in this project`.
- For each of the 149 issues, `Issue.projectsV2` and the search filter `project:` list board 2, but `Issue.projectItems(includeArchived: true)` is empty, the board lists no card, and the issue has no project event. A scratch board accepted the same issue at once, so the fault is bound to board 2.
- Close and reopen of the issue, close and reopen of the board, and ten days of waiting did not clear it. A scan of project item IDs on both sides of the time the issues were created found no card behind the link. Only GitHub can remove the link.
- Each round decides at most 5 of the 46 open issues, with one model call each, fails the write and exits 1. The next round takes 5 more, so the roadmap jobs spend model calls on writes that cannot succeed.

## What Changes

- The roadmap runs on a rebuilt board. The board is a copy of board 2 (`copyProjectV2`), so it has the same fields, options, views and workflows. It is public and linked to the repository, as board 2 was. It holds the "Roadmap run record" draft with its Job record, and a card for each open issue that board 2 held, with Status, Priority, Value, Effort and Job record copied. No closed issue and no pull request moves.
- `.github/roadmap.toml` names the new board in `board`.
- Intake places the 46 open issues on the new board in its next rounds, because the new board has no link to them.
- The change alters no command, option or message. It sets one data value, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Files: `.github/roadmap.toml`.
- Board: a new project board of the owner, and the removal of board 2 after the roadmap has run on the new board.

## Feasibility

- The premise holds. On 2026-10-26 the REST add of #1326 to board 2 answered `Content already exists in this project (HTTP 422)`, the same issue was added to a scratch board at once, and a GraphQL read of the 149 issues showed `projectsV2` set and `projectItems` empty.
- `copyProjectV2` copies the 17 fields, the 4 views and the 8 workflows of board 2, and the draft issues with `includeDraftIssues`. It copies no issue card, so each card is added with `addProjectV2ItemById`, and its values are written with `updateProjectV2ItemFieldValue`.
- A re-read of board 2 and the new board showed no difference in Status, Priority, Value, Effort or Job record for the open issues that both held.

## Existing Tool Considered

The GitHub GraphQL API and its `copyProjectV2` mutation cover the need. GitHub has no mutation that moves a card between boards, and its Support is the only way to remove the dangling link from board 2. This change adds no library and no code.
The change deletes no code.
