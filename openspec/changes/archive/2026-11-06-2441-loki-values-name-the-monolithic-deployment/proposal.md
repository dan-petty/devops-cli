# Proposal

## Why

`k8s/logging/loki-values.yaml` names the deprecated deployment mode `SingleBinary`, which chart `grafana-community/loki` 12.0.0 renamed to `Monolithic`, and it leaves `memcached.enabled` on, so the chart renders a ServiceAccount that nothing uses (#2441).

## What Changes

- `k8s/logging/loki-values.yaml` sets `deploymentMode: Monolithic`.
- The three comments of `k8s/logging/loki-values.yaml` that name the deployment mode say `Monolithic`.
- `tests/commands/k8s/test_k8s.py` has one comment that names `SingleBinary` mode, and the change says `Monolithic` there.
- `k8s/logging/loki-values.yaml` sets `memcached.enabled: false`, so the chart renders no `loki-memcached` ServiceAccount.
- `_loki_mode` in `tests/core/test_k8s_local_path_placement.py` accepts `Monolithic` only and fails on any other name.
- The change carries a spec delta because a Helm values manifest is observable: `loki-release-pin` gains the current mode name and the unused ServiceAccount rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `loki-release-pin`: The Loki values name the deployment mode that the chart documents, The Loki values render no ServiceAccount that no pod uses

## Impact

- Manifests: `k8s/logging/loki-values.yaml`
- Tests: `tests/core/test_k8s_local_path_placement.py`, `tests/commands/k8s/test_k8s.py`

## Feasibility

- read_file `tests/core/test_k8s_local_path_placement.py` lines 1-140 showed `_loki_mode` at line 62 with `if mode not in ("Monolithic", "SingleBinary"):` and `value_at(values, "deploymentMode", "Monolithic")` at line 69, and the docstring at lines 63-64 that names `SingleBinary` as the old name.
- references `SingleBinary` answered `files 4, lines 9`: `k8s/logging/loki-values.yaml` (lines 1, 6, 100, 115), `tests/core/test_k8s_local_path_placement.py` (lines 64, 70), `tests/commands/k8s/test_k8s.py` (line 1771) and `openspec/changes/archive/2026-10-28-1632-loki-grafana-community-chart/design.md` (lines 46, 54). The archived design is a record of a merged change and stays as it is.
- The issue cites `tests/test_k8s_local_path_placement.py`. The probe says commit 513bb31f deleted or renamed it, and the file now lives at `tests/core/test_k8s_local_path_placement.py`, which holds `_loki_mode`. The work is done at that path; the premise of the issue holds.
- list_files `k8s/logging` showed `k8s/logging/kustomization.yaml`, `k8s/logging/loki-values.yaml` and `k8s/logging/networkpolicy.yaml`, so the values file is the one place to edit.
- Command output of the review: `helm pull grafana-community/loki --version 20.0.2` and `helm template` with the base values, with `deploymentMode: Monolithic`, and with `memcached.enabled: false` added. The first two renders are identical, and the third drops the `loki-memcached` ServiceAccount (`templates/memcached/serviceaccount.yaml`) and nothing else. The chart helper `loki.deployment.isMonolithic` accepts both names. The premise holds.
- The first check on the real system: `helm template loki grafana-community/loki --version 20.0.2 -n logging -f k8s/logging/loki-values.yaml`, then confirm the output holds no `kind: ServiceAccount` with `name: loki-memcached` and no other change against the same command on the base commit.
- The second check: `uv run devops ci test tests/core/test_k8s_local_path_placement.py`, which reads the values files and renders no chart.
- The third check: `uv run devops ci test tests/commands/k8s/test_k8s.py`, which holds the Loki retention checks.

## Existing Tool Considered

The open, maintained `grafana-community/loki` Helm chart (version 20.0.2) covers the need: it documents `Monolithic` as the current name of the deployment mode and `memcached.enabled: false` as the way to render no memcached ServiceAccount. The change builds no code of its own, so there is no build, upkeep or fix cost beyond editing one values file and one test function, and no internal code is deleted.
