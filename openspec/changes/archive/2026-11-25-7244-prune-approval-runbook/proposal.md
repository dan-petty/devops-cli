# Proposal: #7244

## Why
Step 13 of `docs/HOMELAB_REPO_SWITCH.md` turns prune on and does not give the approval that homelab uses. Its checks before pull request B cannot pass after pull request A.

## What Changes
Step 13 gives the sync option `Prune=confirm`, the compare of each waiting sync with the accepted list, and the checks of each of the two pull requests. The change alters no behavior that a consumer observes, so it has no spec delta.

## Capabilities
None.

## Impact
Documentation only.

## Feasibility
dan-petty/homelab#228 set the policy. After the approved syncs, the diff check exits 1 only for an Application with another open change, and the prune result check no longer gives 0.

## Existing Tool Considered
None applies: the change is the text of a runbook.
