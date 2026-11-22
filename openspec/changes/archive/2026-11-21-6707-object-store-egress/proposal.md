# Proposal: #6707

## Why
Closes #6707. The admin gRPC port 33646 of SeaweedFS has no authentication, and no release fixes it (GHSA-3qr2-qw48-cj6q). The ingress rules of `object-store-perimeter` admit only the worker pods to it. But the in-namespace egress rule of the perimeter, `to: [podSelector: {}]`, has no ports. The network policy controller of the cluster does not apply the ingress rules of a policy with both types to traffic that an egress rule of the same policy allows, when the policy selects the source and the destination pod (#6707, #6708). So on 2026-11-21 a filer pod connected to TCP 33646 of the admin pod, and to the metrics port 9327 of the admin pod and of the volume pods on other nodes. The `k8s` row passed, because `admin_port_problems` reads only the ingress rules.

## What Changes
- The in-namespace egress rule of `object-store-perimeter` gets the ports of the in-namespace ingress rule: 9333, 19333, 8444, 18444, 8888, 18888, 8333, 18333 and 23646. The ingress rules do not change.
- The new NetworkPolicy `object-store-worker` selects only the worker pods and lets them send to the admin pod on TCP 33646.
- `admin_port_problems` in `tests/gate/k8s_checks/object_store.py` also reads the egress rules. It reports each policy that lets a pod other than the worker send to the admin pod on TCP 33646, also through a rule with no `ports`. It reports a worker that cannot send to the admin pod on TCP 33646.
- Three fixture checks prove the new parts of the rule.
- The Security section of the object store in `k8s/README.md` states the controller behavior and the egress rules.
- The change alters a manifest and the paths of the store pods, so it carries a spec delta.
- The change fits one pull request.

## Capabilities
- `object-store`: MODIFIED requirement "Only the worker reaches the admin gRPC port".

## Impact
- After Argo CD syncs `main`, no pod of namespace `object-store` other than the worker connects to TCP 33646 of the admin pod, and no pod of the namespace connects to the metrics port 9327 of another pod. The worker still connects to TCP 33646, and Alloy still scrapes TCP 9327.
- The components and the operator keep each path that they use between them (Feasibility).
- The other namespaces with the same egress shape stay for #6708.

## Feasibility
- Manifest: on `origin/main` 671f24192, egress rule 2 of `object-store-perimeter` in `k8s/object-store/networkpolicy.yaml` is `to: [podSelector: {}]` with no `ports`.
- Check: `admin_port_problems` calls only `admitted_peers`, which reads the ingress rules.
- Controller: the probe of #6707 and #6708 (temporary namespaces, deleted after the test) gave exit 0 for a client that the ingress rule does not admit, when the source pod had an egress rule `to: [podSelector: {}]` with no ports. With ingress rules only, the same client got exit 1.
- Serving ports: `kubectl -n object-store get pods -o json` (read-only, 13 pods, SeaweedFS 4.54) gives master 9333 and 19333, volume 8444 and 18444, filer 8888 and 18888, S3 8333, admin 23646 and 33646, and the metrics port 9327 on each component. The worker serves only 9327. The operator serves 8080, 8081 and 9443. The S3 gateway also serves gRPC on 18333 (HTTP port plus 10000), which the ingress rule already lists.
- Live paths: the established TCP connections of the 12 SeaweedFS pods on 2026-11-21 (`cat /proc/net/tcp /proc/net/tcp6` in each pod, read-only) give 14 pairs of source component, destination and port. Each pair goes to 9333, 19333, 18444 or 18888, except one: the worker to the admin Service on 33646. The volume HTTP port 8444 and the filer HTTP port 8888 carry the object data when a client reads or writes. All these ports are in the narrowed list.
- Operator: at tag `seaweedfs-operator-0.1.48` (operator 1.0.45), the operator dials the masters through the embedded `weed shell` (`getMasterPeersString`, gRPC 19333), the filer gRPC port 18888 (`swadmin/iam_client.go`, `swadmin/bucket_policy.go`), and the volume gRPC port 18444 when `volumeServer.evacuate` moves the volumes of a volume server before a scale-down. It reads the ready condition of the `Seaweed` CR from the replica counts of the Kubernetes API. All these ports are in the narrowed list.

## Existing Tool Considered
- The NetworkPolicy API of Kubernetes is the tool of the fix. The fix adds rules to it and no code.
- np-guard `netpol-analyzer` (Apache-2.0, maintained) and Cyclonus (MIT) find the connections that policies allow. Both apply the standard rule, in which a connection needs the egress rule of the source and the ingress rule of the destination. So they do not find the path that this controller opens. Cyclonus also needs probe pods on a cluster.
- Build cost: about 40 lines in `tests/gate/k8s_checks/object_store.py` and three fixture checks; about 30k tokens and 45 minutes to build, and a low cost to keep, because the rule uses the port and peer helpers that the module already has.
- The change deletes no internal code.
