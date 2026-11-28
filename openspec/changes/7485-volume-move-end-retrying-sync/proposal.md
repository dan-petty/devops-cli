# Proposal

## Why

The wait of #7464 waited for `status.operationState.finishedAt` of a running sync operation of a paused Application. Between two retries, Argo CD sets `finishedAt` and keeps the phase `Running`: on 2026-11-28 (23:18 UTC on 2026-11-27) Application `danielpetty-com` had `phase=Running`, `finishedAt=23:18:04`, `retryCount=2`, and its next attempt ran at 23:18:24. So the wait ended at once and the operation went on, which can make a deleted claim again from git (#7485).

## What Changes

- While the phase is `Running` or `Terminating`, the run ends the operation with a patch of `status.operationState.phase` to `Terminating`, as `argocd app terminate-op` does, and waits for the phase `Failed`. When the wait times out, it reads the phase again: an operation that ended in another phase is done; one that still runs fails the step before the point of no return.
- The dry run lists the patch and the wait.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move ends the running syncs of the paused Applications.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node, step 1)

## Feasibility

- Read on the homelab, 2026-11-27 23:18 UTC: the patch `{"status":{"operationState":{"phase":"Terminating"}}}` on Application `danielpetty-com` ended its retrying operation; the phase became `Failed` with the message `Operation terminated (retried 2 times).` within seconds.

## Existing Tool Considered

The end of an operation is the same field that `argocd app terminate-op` sets; `kubectl wait` waits for the phase. About 6k tokens and 30 minutes.

## Dependencies

None.
