# Proposal

## Why

Issue #2147: the Grafana, Prometheus server, and Loki volumes sit on the control-plane node, whose 236 GB root disk is about 79% used. The three workloads are in the placement exemption list, so the test does not check their affinity. Moving them to worker nodes and adding the affinity frees the control-plane disk and closes the exemption gap left by #1634.

## What Changes

- Add the control-plane DoesNotExist node affinity to monitoring/grafana-values.yaml (key affinity), monitoring/prometheus-values.yaml (key server.affinity), and logging/loki-values.yaml (key singleBinary.affinity).
- Remove the three entries (grafana, prometheus-server, storage-loki-0) from CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS in src/devops_cli/config/constants.py.
- Remove the three entries from _CONTROL_PLANE_CLAIM_EXEMPTIONS in tests/test_k8s_local_path_placement.py so the test checks the affinity for all three workloads.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: grafana-prometheus-loki-control-plane-affinity

## Impact

- Code: `monitoring/grafana-values.yaml`, `monitoring/prometheus-values.yaml`, `logging/loki-values.yaml`, `src/devops_cli/config/constants.py`
- Tests: `tests/test_k8s_local_path_placement.py`

## Feasibility

- The README section Local-Path Volume Placement confirms the affinity pattern, the exemption mechanism, and the move procedure. The three values files and the constants file are named in the issue and the README.
- The test tests/test_k8s_local_path_placement.py is named in the README and the issue. It currently passes with the three workloads in the exemption list.
- First check: run uv run devops ci test tests/test_k8s_local_path_placement.py to confirm the test passes with the current exemptions.
- Second check: read monitoring/grafana-values.yaml, monitoring/prometheus-values.yaml, and logging/loki-values.yaml to confirm the affinity is not yet present.
- Third check: read src/devops_cli/config/constants.py to confirm the three entries are in CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS.

## Existing Tool Considered

No external tool covers this. The change edits YAML values files and a Python constants file in this repository. The operational volume move uses the project's own devops k8s volume move command, described in k8s/README.md.
