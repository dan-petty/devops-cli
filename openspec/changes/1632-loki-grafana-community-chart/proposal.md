# Proposal

## Why

Issue #1632: Loki runs 3.6.11 from chart `grafana/loki` 7.3.0 in `https://grafana.github.io/helm-charts`. That chart is now the Grafana Enterprise Logs chart, and its newest version, 7.5.0, still runs Loki 3.6. CVE-2026-21729 affects Loki before 3.7.0: the `detected_fields` endpoint allocates memory for the `limit` that the request gives, so one request with a very large limit stops Loki. No 3.6 release has the fix.

Loki runs with `auth_enabled: false`. The NetworkPolicy of `logging` admits port 3100 from Grafana, the Alloy collectors and the OpenTelemetry Collector, so a pod in those releases or a user of Grafana that has signed in can send that request. Grafana Logs Drilldown uses `detected_fields`.

The open-source chart continues as `grafana-community/loki` in `https://grafana-community.github.io/helm-charts`.

## What Changes

- The Argo CD Application `loki` (`k8s/argocd/apps/loki.yaml`) installs chart `loki` 20.0.2 from `https://grafana-community.github.io/helm-charts`. Chart 20.0.2 runs Loki 3.7.9.
- The `logging` stack of `devops k8s deploy-stack` adds the `grafana-community` repository in place of `grafana`, and installs `grafana-community/loki` 20.0.2.
- `k8s/logging/loki-values.yaml` names the new chart in its header and deletes `monitoring.selfMonitoring`, which the chart removed in 9.0.0. The note of #1133 on `deletion_mode` names Loki 3.7.9 and its source lines, because the behavior that it records did not change.
- A new test in `tests/test_k8s_logging_stack.py` holds the repository, the chart and the version of both paths, and the removed key.
- The change carries a spec delta, because a manifest, the chart that `devops k8s deploy-stack` installs and the Loki release that runs are observable. It creates the capability `loki-release-pin`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `loki-release-pin`: Argo CD and deploy-stack install `grafana-community/loki` 20.0.2, which runs Loki 3.7.9, and the values set no key that the chart removed.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/argocd/apps/loki.yaml`, `k8s/logging/loki-values.yaml`. Argo CD tracks `main` with prune and self-heal, so the merge changes the live cluster: Argo CD syncs Application `loki` to the new chart.
- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py` (the Helm repositories and the release of the `logging` stack).
- Tests: `tests/test_k8s_logging_stack.py`, `tests/test_k8s_local_path_placement.py`.
- Rollout: StatefulSet `loki` has one replica. Argo CD changes its pod template, so pod `loki-0` stops and starts again with the new image. Loki does not accept logs for the time of the restart, and the Alloy collectors send the logs again when Loki is ready. The selector, the service name and the claim template do not change, so the new pod mounts the same claim `storage-loki-0` (design.md).

## Feasibility

- The grafana.com advisory for CVE-2026-21729 ("Loki detected_fields query limits results in unbounded memory allocation", published 2026-07-15) gives CVSS 7.5 and "Fixed Versions: >=3.7.0". The GitHub advisory GHSA-65p5-8cm9-qcxx gives the same CVE and score.
- `kubectl get sts -n logging` on 2026-10-28 shows image `docker.io/grafana/loki:3.6.11`. Application `loki` is Synced and Healthy at chart 7.3.0.
- `helm search repo grafana/loki --versions` shows 7.5.0 (app 3.6.16) as the newest chart, with the description "Helm chart for Grafana Enterprise Logs". `helm show values grafana/loki --version 7.5.0` still sets `loki.image.tag: 3.6.11`.
- `helm search repo grafana-community/loki --versions` shows 20.0.2 (app 3.7.9) as the newest chart. Chart 9.3.2 is the first that runs Loki 3.7.
- The upgrade notes in the README of chart 20.0.2 and the Loki guide "Upgrade from the Loki Helm chart to the Community Helm chart" list the breaking changes from 6.x to 20.0.0. The only one that touches these values is the removal of `monitoring.selfMonitoring` in 9.0.0 (design.md).
- `helm template` of chart 20.0.2 with the changed values renders image `docker.io/grafana/loki:3.7.9`. Its StatefulSet has the same selector, service name, pod management policy and claim template (`storage`, ReadWriteOnce, 20Gi) as the render of chart 7.3.0.
- `kubectl apply --dry-run=server -n logging` of that render on 2026-10-28 reports each object as `configured` or `created` and gives no warning. Namespace `logging` enforces the `baseline` Pod Security level.
- The source of Loki v3.7.9 (`pkg/loki/modules.go`, `pkg/compactor/generationnumber/gennumber_loader.go`, `pkg/compactor/deletion/grpc_request_handler.go`) holds the same cache generation lookup as v3.6.11, so the #1133 note on `deletion_mode` stays true with new line numbers.

## Existing Tool Considered

The upstream Loki release and the community Helm chart cover the need. The change builds no code. It deletes the pin of the Grafana Enterprise Logs chart from the `logging` stack and from the Argo CD Application, and the `monitoring.selfMonitoring` block of the values.
