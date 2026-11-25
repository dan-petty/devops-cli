# Proposal: #4992

## Why

No offline check enforces the rule in `openspec/specs/llm-valkey/spec.md` that every Valkey container keeps its `--maxmemory` bound at most three quarters of its container memory limit (`256mb / 384Mi`, `512mb / 768Mi`, `1536mb / 2048Mi`). Because environment manifests under `k8s/` moved to `dan-petty/homelab` (`tests/gate/k8s_checks/environment_freeze.py`), container sizing is deferred to `#7140` and `dan-petty/homelab#109`, while this change adds the offline `--maxmemory` ratio gate check to `devops ci --check --only k8s`.

## What Changes

- Add `tests/gate/k8s_checks/valkey_memory.py` to the `k8s` gate row (`tests/gate/k8s.py`).
- Parse rendered workloads across every Argo CD path application (`discover_path_applications`), detect containers running `valkey-server` directly or inside a `sh -c` entrypoint, parse `--maxmemory` (`kb`/`mb`/`gb` as 1024-based bytes) and `resources.limits.memory` (`kubernetes.utils.quantity.parse_quantity`), and fail when the bound exceeds three quarters of the memory limit.
- Ignore `valkey-server` containers without `--maxmemory` and include negative-control `check_*` cases inside `tests/gate/k8s_checks/valkey_memory.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-valkey`: Enforce the three-quarters `--maxmemory` to container memory limit ratio across rendered manifests in the `k8s` gate row.

## Impact

- Gate checks: `tests/gate/k8s_checks/valkey_memory.py` (new module auto-discovered by `tests/gate/k8s.py`)
- Manifests: none (`k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml`, and `k8s/llm/valkey-runs.yaml` already comply; sizing deferred to `#7140`)

## Feasibility

Confirmed against `k8s/llm/valkey.yaml` (`1536mb` vs `2048Mi` = 0.75), `k8s/llm/valkey-devops.yaml` (`256mb` vs `384Mi` = 0.667), `k8s/llm/valkey-runs.yaml` (`512mb` vs `768Mi` = 0.667), `tests/gate/k8s_render.py`, and `tests/gate/runner.py` (auto-discovers modules under `tests/gate/k8s_checks/`).

## Existing Tool Considered

Adopted `robusta-dev/krr` (MIT) in `#4992` for the cluster sizing work deferred to `#7140` / `dan-petty/homelab#109`, and reused `kubernetes.utils.quantity.parse_quantity` plus `tests/gate/k8s.py` (`kubectl kustomize`) for the offline ratio gate check that KRR lacks.
