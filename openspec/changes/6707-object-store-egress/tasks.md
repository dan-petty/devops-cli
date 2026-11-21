# Tasks

## 1. The egress side of the admin port (behavior)

- [x] 1.1 Write the fixture checks: the committed policies with no `ports` in the in-namespace egress rule of `object-store-perimeter`, a fixture policy that lets the filer pods send to the admin pod on 33646, and the committed policies without `object-store-worker`
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Extend `admin_port_problems` to the egress rules, with the helper `egress_senders` and one shared helper for the policies that select a pod for egress
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.3 Give the in-namespace egress rule of `object-store-perimeter` the ports of its in-namespace ingress rule, and add `object-store-worker`
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Documents

- [ ] 2.1 Write the controller behavior and the egress rules in the Security section of the object store in `k8s/README.md`, and name the three NetworkPolicies in its Application table
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The other namespaces with an in-namespace egress rule with no ports, and the general `k8s` row for that shape: #6708.

## Checks after the sync

- Pending a person: after Argo CD syncs `main`, `kubectl -n object-store exec seaweedfs-filer-0 -- nc -z -w 3 seaweedfs-admin 33646` exits 1, the same command from `deploy/seaweedfs-worker -c worker` exits 0, and `kubectl -n object-store exec seaweedfs-filer-0 -- nc -z -w 3 <volume pod IP> 9327` exits 1 for a volume pod on another node.
- Pending a person: after the sync, `kubectl -n object-store get seaweed seaweedfs -o jsonpath='{.status.conditions[0].message}'` prints `Seaweed cluster is ready`, and the 13 pods are Ready.
