# Design

## Decisions
- Return exit code 1 with `pods "<name>" not found` in `FakeCluster._read_pod_single` when a queried pod name does not match any CloudNativePG cluster.
- In `test_an_agent_stops_before_the_control_plane_node`, explicitly set `HOSTNAME` via `monkeypatch` to ensure the test isolates cluster pod lookup from container hostname.

## Rejected alternatives
- Set synthetic pod on `node-2` instead of `node-1`: A cluster double must return not-found for nonexistent pods rather than arbitrary cluster nodes.
- Unset `HOSTNAME` in `agent_caller` fixture: In real containerized workloads, `HOSTNAME` is set by the container runtime; production code in `current_pod_node()` queries Kubernetes to verify if that hostname corresponds to an actual pod in the cluster, and `FakeCluster` should accurately reflect when it does not.
