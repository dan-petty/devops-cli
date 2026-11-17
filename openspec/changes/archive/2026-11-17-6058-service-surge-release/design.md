# Design

## Decisions
- One replica with `maxSurge: 1` and `maxUnavailable: 0`. Two pods run only during a release. The PV of the home volume binds to one node, so the scheduler puts the new pod on that node, and both pods mount the ReadWriteOnce volume.
- The Lease `roadmap-service-rows` guards the rows. A pod takes it when it does not exist, has no holder, or was not renewed for its `leaseDurationSeconds`. Each write sends the `resourceVersion` of the last read, so the API server refuses one of two writes at the same time. The times are the defaults of client-go: a call ends after 5 s, the holder stops at a renew deadline of 10 s, the Lease lasts 15 s, and a pod tries again each 2 s.
- Readiness does not wait for the Lease. If it did, the new pod would never be ready, and with `maxUnavailable: 0` the old pod would never stop.
- A pod that waits keeps each delivery in the queue of its lanes. The workers and the poll start when it takes the Lease, after it reads the budget window, the halt, the ledger of failed rounds, and removes the retired lane state.
- The drain waits for the workers in a thread, so the event loop renews the Lease until the rounds end. Then the pod gives the Lease back, and the next pod takes it within 2 s. When a round is still in flight after the cut wait, the pod keeps the Lease, which ends 15 s after its last renewal.
- A holder that cannot renew for 10 s stops its workers and its poll, and cuts the budget, so a round in flight ends at its next GitHub request. `/healthz` then fails, and the kubelet starts the container again.
- The pod name from the downward API is the holder identity and `service.instance.id`. A restarted container of the same pod holds the same identity, so it takes its own Lease at once.
- The timeouts nest: preStop 10 s + drain 600 s + cut 30 s + release call 5 s = 645 s, inside the grace period of 660 s.
- RBAC: `get` and `update` with `resourceNames: [roadmap-service-rows]`, and `create` with no name, because the API server checks a create before the object has a name.

## Rejected alternatives
- Two replicas and a PodDisruptionBudget now: the PodDisruptionBudget would stop each drain of the node of the volume, and a delivery to the pod with no Lease would wait for a poll. #4575 does this with a stateless router.
- Readiness that waits for the Lease: the rollout stops.
- The leader election of the `kubernetes` client: version 36.0.3 has no Lease lock, and version 37 changes each model of the client. Neither loop stops or gives the Lease back.
- A fixed `service.instance.id`: two pods of a surge release would send deltas into one stream, and the collector drops the points of the older stream.
- A test that reads the manifest: the owner rule of 2026-11-16 (#6060). `kubectl kustomize` with kubeconform checks the manifest, and the live check reads the hook deliveries and the holder of the Lease.
