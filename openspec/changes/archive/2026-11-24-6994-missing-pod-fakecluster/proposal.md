# Proposal: #6994

## Why
In `tests/support/infra.py`, `FakeCluster._read_pod_single` returns a synthetic pod on `node-1` for unknown pods.
When `Service Image Tests` runs in Docker, `HOSTNAME` holds the container name.
`current_pod_node` reads `HOSTNAME` and queries `kubectl get pod $HOSTNAME`.
`FakeCluster` falsely places this pod on `node-1`.
In `test_an_agent_stops_before_the_control_plane_node`, `_apply_alone` sees that the host node matches the pod node and stops with `node-1.example.com (node-1) is its pod node` instead of checking the control plane.
This defect causes `Service Image Tests (shard 1 of 6)` to fail on Renovate pull requests (#6986, #6987, #6989, #6991).

## What Changes
- Return exit code 1 with `pods "<name>" not found` in `FakeCluster._read_pod_single` when the requested pod is not in `cnpg_clusters`.
- Set `HOSTNAME` in `test_an_agent_stops_before_the_control_plane_node` via `monkeypatch` to prevent regressions when tests run inside containers.
- This change alters no behavior that external consumers observe, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`.

This change fits one pull request.

## Capabilities
- Accurate missing-pod responses in test cluster double `FakeCluster`.

## Impact
- `Service Image Tests (shard 1 of 6)` passes inside Docker containers.
- No breaking changes.

## Feasibility
- Verified against real CI runs: Renovate PRs #6986, #6987, #6989, and #6991 failed `Service Image Tests (shard 1 of 6)` with this exact `AssertionError`.
- Verified that returning not found for unknown pods resolves the failure and makes all 49 tests in `tests/commands/test_infra_apply.py` pass.

## Existing Tool Considered
- Existing test helper `FakeCluster` in `tests/support/infra.py`. No new tool is required. Deletes zero internal files.
