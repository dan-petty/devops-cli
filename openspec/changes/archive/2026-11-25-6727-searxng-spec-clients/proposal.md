# Proposal: #6727

## Why

The requirement `Only the roadmap Service calls the pod` in `openspec/specs/searxng-service/spec.md` says that only `searxng-clients` allows egress to port 8080 in namespace `devops`, and its heading names only the roadmap Service. Since #5483, the stage Job pods also reach SearXNG through `searxng-stage-clients`, so that requirement disagrees with `k8s/devops/searxng/networkpolicy-client.yaml`. Closes #6727.

## What Changes

- Rename requirement `Only the roadmap Service calls the pod` in `openspec/specs/searxng-service/spec.md` to `Only the roadmap Service and stage Jobs call the pod`.
- Update the requirement and its scenario to name the roadmap-service pods and the stage Job pods as the only service clients, and to name `searxng-clients` and `searxng-stage-clients` as the only egress policies to port 8080 in namespace `devops`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `searxng-service`: Rename and update the client access requirement to name the roadmap-service pods, the stage Job pods, `searxng-clients`, and `searxng-stage-clients`.

## Impact

- Specs: `openspec/specs/searxng-service/spec.md` via OpenSpec archive.
- Code and manifests: None; `k8s/devops/searxng/networkpolicy.yaml`, `k8s/devops/searxng/networkpolicy-client.yaml`, `docs/CLUSTER.md`, and `tests/gate/k8s_checks/network_policies.py` already match the cluster state.

## Feasibility

- Inspected `openspec/specs/searxng-service/spec.md:38-47`, which still names only `searxng-clients` at line 39 and uses the title `Only the roadmap Service calls the pod` at line 38.
- Inspected `k8s/devops/searxng/networkpolicy-client.yaml:8-50`, which defines both `searxng-clients` for `app.kubernetes.io/name: roadmap-service` and `searxng-stage-clients` for `app.kubernetes.io/name: devops-cli-job` with `app.kubernetes.io/component: roadmap-stage`, both targeting TCP port 8080 on SearXNG.
- Verified that `docs/CLUSTER.md:257` and `tests/gate/k8s_checks/network_policies.py:210-221` already reflect both clients and both policies.
- First check against the real system: `uv run devops ci --check --only openspec` validates the change and the archived spec.

## Existing Tool Considered

The alternatives check of 2026-11-22 in #6727 recorded `not-applicable` for class `docs` and named no external tool. This change uses `openspec` (`npx openspec validate` and `devops openspec archive`) to update the living spec from the delta, with no custom Python code to write or keep.
