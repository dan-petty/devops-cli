# Proposal

## Why

The Grafana container read the renderer token through a required `secretKeyRef`. The Secret exists only after `devops k8s push-secrets`, which a person runs. Argo CD applied the renderer values before the Secret existed, and the Grafana pod stopped in `CreateContainerConfigError`, so a feature of panel images stopped the whole Grafana service (#5200).

## What Changes

- `k8s/monitoring/grafana-values.yaml` repeats `GF_RENDERING_RENDERER_TOKEN` under `envValueFrom` with `optional: true`. The chart writes its required entry first; the kubelet takes the last entry, so Grafana starts without the Secret.
- The renderer Deployment keeps its required reference, because it has no use without the token.
- `src/devops_cli/k8s/cluster_secrets.py` gains `OPTIONAL_FEATURE_SECRETS`, which names `monitoring/grafana-image-renderer`.
- `k8s/README.md` says that a pull request which adds a Secret reference names the push command as its first line.
- Add `tests/k8s/test_grafana_renderer_optional.py`: a `helm template` render, and the Secret of the optional list.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `grafana-image-renderer`: a missing renderer token stops only panel images.

## Impact

- Manifests: `k8s/monitoring/grafana-values.yaml`, `k8s/README.md`
- Code: `src/devops_cli/k8s/cluster_secrets.py`
- Tests: `tests/k8s/test_grafana_renderer_optional.py`, `tests/support/helm.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. The chart 14.4.1 writes the required entry at `templates/_pod.tpl:1673`, and `envValueFrom` entries follow it.
- The values file already holds `envValueFrom` for `grafana-admin`, so the token entry joins that block.
- A render with `helm template grafana grafana-community/grafana --version 14.4.1 -f k8s/monitoring/grafana-values.yaml` shows the optional entry last.
- Kubernetes takes the last value when a container holds two entries of one env name.
- `uv run pytest tests/k8s` and `uv run python -m tests.gate.k8s` pass after the change.

## Existing Tool Considered

The chart holds no value for `optional` on this reference at 14.4.1. A duplicate optional entry and the documented kubelet order need no tool, and a chart upgrade can replace it. The change costs about 1,500 tokens to build and 100 a quarter to keep.

## Dependencies

None.
