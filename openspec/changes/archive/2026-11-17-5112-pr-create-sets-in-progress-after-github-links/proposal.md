# Proposal: #5112

## Why

`devops pr create` reads `closingIssuesReferences` immediately after GitHub opens the pull
request. GitHub links the closing issue asynchronously, so the read can return no issue.
`set_delivered_status` returns None, the command prints nothing, and the issue keeps its old
Status until `devops pr ready` sets In Review. Closes #5112.

## What Changes

- `devops pr create` reads the closing issues again for a bounded time after the pull request
  opens, using dedicated poll constants.
- When the bounded wait ends with no linked issue, the command warns and exits 0, because the
  pull request was created.
- `set_delivered_status` returns the number of the issue whose Status it sets, so the command
  can tell a write from a missing link.

## Capabilities

### Modified

- `roadmap-item-labels`: the Status follows the pull request that delivers the item, including
  GitHub's asynchronous link to the closing issue.

## Impact

`devops pr create` takes up to about 25 seconds longer when GitHub links no closing issue, and
it no longer leaves the issue at its old Status without a message. A pull request that closes
no issue still changes no label.

## Feasibility

Confirmed against the issue and the code: `_finish_created_pr` calls `_status_recorded`, which
calls `set_delivered_status`; that function already returns the number of the issue whose
Status it moves. The retry follows the existing `DEFAULT_PR_UPDATE_HEAD_POLL_*` pattern.

## Existing Tool Considered

No open tool or library waits for GitHub's asynchronous issue link and writes the roadmap
Status. The change adds no dependency: about 20,000 to 40,000 tokens and one to two days to
build, keep and fix.
