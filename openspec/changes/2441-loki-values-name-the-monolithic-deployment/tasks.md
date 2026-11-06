# Tasks

## 1. Name the current Loki deployment mode in the values and turn memcached off

Reads: `k8s/logging/loki-values.yaml`, `tests/commands/k8s/test_k8s.py`. Changes: `k8s/logging/loki-values.yaml`, `tests/commands/k8s/test_k8s.py`.

- [x] 1.1 In `k8s/logging/loki-values.yaml` set `deploymentMode: Monolithic`. Change the first line comment and the comments above `sidecar` and `read` to say `Monolithic` instead of `SingleBinary`. Add a `memcached:` block with `enabled: false` beside the `chunksCache` and `resultsCache` blocks, with a comment that says no memcached pod uses the ServiceAccount that the chart renders by default. Change no other key. In `tests/commands/k8s/test_k8s.py`, change the comment at line 1771 from `SingleBinary mode` to `Monolithic mode`
  - Verification: `! git grep -n SingleBinary k8s/ tests/commands/` (exits 0 when it finds nothing), and `helm template loki grafana-community/loki --version 20.0.2 -n logging -f k8s/logging/loki-values.yaml` renders no `loki-memcached` object and differs from the base render by that ServiceAccount only

## 2. Make the Loki claim test accept Monolithic only

Reads: `tests/core/test_k8s_local_path_placement.py`, `tests/support/k8s_tree.py`, `k8s/logging/loki-values.yaml`. Changes: `tests/core/test_k8s_local_path_placement.py`.

- [x] 2.1 In `_loki_mode` in `tests/core/test_k8s_local_path_placement.py`, accept `Monolithic` only: fail when `deploymentMode` is anything else, including `SingleBinary`. Rewrite the docstring to say that `Monolithic` is the mode of the grafana-community chart and that the other modes run write and backend StatefulSets whose claims the table does not name. Keep the `singleBinary.persistence.enabled` read and the rest of the module unchanged. Add a test beside it that gives `_loki_mode` a values dict with `deploymentMode: SingleBinary` and asserts `pytest.fail` (`Failed`) with `match=` on `Loki deploymentMode SingleBinary`, and one that gives it `Monolithic` and asserts a true answer
  - Verification: `uv run devops ci test tests/core/test_k8s_local_path_placement.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
