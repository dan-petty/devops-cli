# Design

## Decisions

- **Edit the values at `k8s/logging/loki-values.yaml` and the test at `tests/core/test_k8s_local_path_placement.py`, the path that holds `_loki_mode` today.**: The probe reports that commit 513bb31f renamed `tests/test_k8s_local_path_placement.py`, and the file at the new path holds the function the issue names.
- **Set `deploymentMode: Monolithic` and name `Monolithic` in each comment of the file that names the mode.**: The chart renamed the mode in 12.0.0 and keeps `SingleBinary` only as a deprecated alias, so the values name the current mode.
- **`_loki_mode` accepts `Monolithic` only and fails on every other name.**: The repository controls its own values file, so the test holds the one name that the chart documents and fails when a later chart drops the alias.
- **Set `memcached.enabled: false` rather than leave the chart default.**: `chunksCache` and `resultsCache` are off, so the rendered ServiceAccount `loki-memcached` has no pod and the values say so.
- **Keep the archived change `2026-10-28-1632-loki-grafana-community-chart` and its text as it is.**: An archive records a merged change; `references` shows its design.md lines 46 and 54 describe what that change did, not what the repository holds now.

## Rejected alternatives

- **Accept both `Monolithic` and `SingleBinary` in `_loki_mode`, as the chart does.**: `tests/core/test_k8s_local_path_placement.py` line 70 currently reads `if mode not in ("Monolithic", "SingleBinary"):`, and the issue asks for `Monolithic` only; a test that keeps the alias fails to hold the values file when the chart drops it.
- **Delete `loki-ingress` or other Loki objects in this change.**: `k8s/logging` holds only `kustomization.yaml`, `loki-values.yaml` and `networkpolicy.yaml`, and the issue asks for two value keys and one test function.
- **Add a new test module that reads the values file for the two keys.**: `_loki_mode` in `tests/core/test_k8s_local_path_placement.py` already reads `deploymentMode` from the values file through `value_at`, so a second reader copies it.
