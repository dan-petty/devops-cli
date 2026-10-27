# Proposal

## Why

Issue #2046: `k8s/llm/portkey/configmap.yaml` mounts a routing config at `/app/config.json` in the Portkey gateway pod. The Portkey gateway 1.15.0 does not read `/app/config.json`. The gateway takes routing configurations through request headers such as `x-portkey-config`, not through a static JSON file. The ConfigMap is unused and has no effect on live traffic.

## What Changes

- Delete the unused `k8s/llm/portkey/configmap.yaml` manifest.
- Remove the unused `config-volume` mount and volume from `k8s/llm/portkey/deployment.yaml`.
- Remove `portkey/configmap.yaml` from `k8s/llm/kustomization.yaml` and `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Update `tests/test_ai_gateway_portkey.py` to assert that the unused ConfigMap is gone and not mounted.
- Update `tests/test_k8s.py` dry-run assertions to match the updated manifests.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/llm/portkey/configmap.yaml`, `k8s/llm/portkey/deployment.yaml`, `k8s/llm/kustomization.yaml`.
- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Tests: `tests/test_ai_gateway_portkey.py`, `tests/test_k8s.py`.

## Feasibility

- Source review of `portkeyai/gateway:1.15.0` confirms that `/app/build/start-server.js` contains no reference to `config.json`.
- Upstream documentation confirms that the Portkey gateway reads routing rules dynamically through the `x-portkey-config` request header.
- No in-cluster service or client relies on the mounted `/app/config.json` file.
- The existing manifest test can assert that the file is gone and unmounted from the deployment.

## Existing Tool Considered

No outside tool applies. The change removes an unused Kubernetes ConfigMap and cleans up references in the deployment manifest and stack lifecycle.
