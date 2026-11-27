# Proposal

## Why

`devops k8s volume move` paused Argo CD by turning off automated sync. A sync operation that already ran went on after that. On 2026-11-27 a sync of Application `gitea`, which started while Argo CD was resumed after a stranded move, went on after the pause, made the deleted claim `gitea-shared-storage` again from git with an empty volume, and scaled Gitea up on it (dan-petty/homelab#472). After a merge of a class change, the automated sync fails on the immutable claim and retries, so a move soon after the merge meets such an operation (#7464).

## What Changes

- After the pause, and again before the delete of the copy pods (step 8), the run reads `status.operationState.phase` of each paused Application. While it is `Running` or `Terminating`, it runs `kubectl wait application/<name> --for=jsonpath={.status.operationState.finishedAt}` with a bound of `DEFAULT_K8S_VOLUME_MOVE_SYNC_WAIT_SECONDS` (600 s).
- A wait that times out fails the step before the point of no return, so the run undoes its steps and resumes Argo CD.
- The dry run lists the read and the wait at both places.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: a volume move waits for the running syncs of the paused Applications.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node, step 1)

## Feasibility

- Read on the homelab, 2026-11-27: the operation of `gitea` had `startedAt` 19:47:53, two retries, and `finishedAt` 19:48:27; `automated.enabled` was `false` from 19:48:04.
- `kubectl wait application/bootstrap -n argocd --for=jsonpath='{.status.operationState.finishedAt}'` ends at once when the field exists, and times out when it does not (kubectl v1.37.3).
- An operation retries up to 5 times with a backoff of up to 3 minutes in the Applications of the homelab, so 600 s holds a full retry series.

## Existing Tool Considered

`kubectl wait` with a JSONPath condition waits for the end of the operation; no loop of reads is needed. About 8k tokens and 40 minutes.

## Dependencies

None.
