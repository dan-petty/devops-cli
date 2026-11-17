# Design

## Decisions
- `RollingUpdate` with `maxSurge: 1` and `maxUnavailable: 0`, and one replica. The old pod stays available until the new pod passes `/readyz`, so one pod always takes the webhooks during a release.
- The volume stays. The scheduler puts the new pod on the node of the PV, because the PV has a node affinity for that node, and ReadWriteOnce lets two pods of one node mount the claim. The `local-path` PV is a `hostPath` volume, so no attach step refuses a second mount.
- The Lease `roadmap-service-rows` of #6058 keeps the rows to one pod. The new pod reports ready, keeps each delivery in its lane queues, and runs the rows when the old pod gives the Lease back at the end of its drain.
- The kube-linter exception of `no-rolling-update-strategy` goes, so the `kube-linter` row of `devops ci` checks the strategy. No test reads the manifest (#6060).

## Rejected alternatives
- Two replicas and a PodDisruptionBudget: the evicted pod cannot start on another node, so the budget would stop each drain of the node of the volume. #4575 does this with a stateless router that holds no volume.
- `maxSurge: 0` and `maxUnavailable: 1`: the old pod stops before the new pod is ready, so the gap stays.
- `ReadWriteOncePod` on the claim: it allows one pod only, so the new pod could not start during the surge.
- A node selector for the node of the volume on the Deployment: the PV node affinity already does this, and a node name in git is a private name.
