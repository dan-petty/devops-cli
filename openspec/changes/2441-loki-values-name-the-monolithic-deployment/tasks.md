# Tasks

## 1. Name the current Loki deployment mode in the values and turn memcached off

Reads: `k8s/logging/loki-values.yaml`, `tests/core/test_k8s_local_path_placement.py`. Changes: `k8s/logging/loki-values.yaml`.

- [ ] 1.1 In `k8s/logging/loki-values.yaml` set `deploymentMode: Monolithic`. Change the first line comment and the comments above `sidecar` and `read` to say `Monolithic` instead of `SingleBinary`. Add a `memcached:` block with `enabled: false` beside the `chunksCache` and `resultsCache` blocks, with a comment that says no memcached pod uses the ServiceAccount that the chart renders by default. Change no other key
  - Verification: `uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes

## 2. Make the Loki claim test accept Monolithic only

Reads: `tests/core/test_k8s_local_path_placement.py`, `tests/support/k8s_tree.py`, `k8s/logging/loki-values.yaml`. Changes: `tests/core/test_k8s_local_path_placement.py`.

- [ ] 2.1 In `_loki_mode` in `tests/core/test_k8s_local_path_placement.py`, accept `Monolithic` only: fail when `deploymentMode` is anything else, including `SingleBinary`. Rewrite the docstring to say that `Monolithic` is the mode of the grafana-community chart and that the other modes run write and backend StatefulSets whose claims the table does not name. Keep the `singleBinary.persistence.enabled` read and the rest of the module unchanged
  - Verification: `uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes

## 3. Write the change folder and archive it

Reads: `openspec/specs/loki-release-pin/spec.md`, `openspec/changes/archive/2026-10-28-1632-loki-grafana-community-chart/proposal.md`. Changes: `openspec/changes/2441-loki-monolithic-mode-and-no-memcached-service-account/proposal.md` (new), `openspec/changes/2441-loki-monolithic-mode-and-no-memcached-service-account/design.md` (new), `openspec/changes/2441-loki-monolithic-mode-and-no-memcached-service-account/tasks.md` (new), `openspec/changes/2441-loki-monolithic-mode-and-no-memcached-service-account/specs/loki-release-pin/spec.md` (new), `openspec/changes/2441-loki-monolithic-mode-and-no-memcached-service-account/.openspec.yaml` (new).

- [ ] 3.1 Write the proposal, design, tasks and the `loki-release-pin` spec delta of the change in `openspec/changes/2441-loki-monolithic-mode-and-no-memcached-service-account/`, with the two added requirements and their scenarios. Tick each task as its group lands, and archive the folder into `openspec/changes/archive/` in the last commit
  - Verification: `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
