# Design

## Where the release lives

Two places pin the Loki chart. `k8s/argocd/apps/loki.yaml` names the repository, the chart and the version that Argo CD installs. The `logging` entries of `_HELM_REPOS_BY_STACK` and `_HELM_RELEASES_BY_STACK` in `src/devops_cli/commands/k8s/stack_lifecycle.py` name the repository that `devops k8s deploy-stack --stack logging` adds and the chart and version that it installs. Both move to `grafana-community/loki` 20.0.2 in this change. The `logging` stack adds only `grafana-community`, because Loki is the only release of that stack. The `infra` stack keeps `grafana` for `k8s-monitoring` and `pyroscope`.

The chart sets the Loki image tag from its `appVersion` when the values set no image. Two value blocks can set the tag or a digest of the single binary: `loki.image` and `singleBinary.image`. The values set neither, and the Application gives the chart no value but the values file. So the chart version is the Loki pin: 20.0.2 runs `docker.io/grafana/loki:3.7.9`. A test holds this, because one line in either block can bring back a Loki release before 3.7.0 with the chart pin unchanged.

## Why 20.0.2

The issue names 18.17.1 (Loki 3.7.8). On 2026-10-28, 20.0.2 (Loki 3.7.9) is the newest chart, and its upgrade notes are safe for these values:

- 18.x to 19.0.0: the headless Service no longer inherits the labels and annotations of the main Service. These values set none.
- 19.2.x to 19.3.0: the pod templates no longer carry `helm.sh/chart` and `app.kubernetes.io/version`. No rule, dashboard or scrape selector here reads those pod labels. The Loki integration of k8s-monitoring selects `app.kubernetes.io/name: loki` and `app.kubernetes.io/component: single-binary`, which the pods still carry.
- 19.x to 20.0.0: the MinIO subchart is gone, and the values schema refuses an unknown top-level key. These values do not use MinIO, and `helm template` accepts every top-level key of the values. It also accepts `serviceAccount.automountServiceAccountToken`, which a parallel change adds to the same file.

The notes from 6.x to 18.x need one change to these values, the removal of `monitoring.selfMonitoring` in 9.0.0. The 18.0.0 change of the metric label `cluster` to `app_instance` applies only to the chart's own ServiceMonitor, rules and dashboards, which these values do not turn on. The Loki alerts in `k8s/monitoring/prometheus-values.yaml` do not filter on `cluster`.

## What the new render changes

`helm template` of 7.3.0 and of 20.0.2 with the values renders the same objects, and one more: ServiceAccount `loki-memcached` with `automountServiceAccountToken: false`. The chart renders it because `memcached.enabled` is `true` by default. No pod uses it, because `chunksCache` and `resultsCache` are off. #2441 turns it off.

The StatefulSet keeps the fields that Kubernetes does not let a change touch: the selector, `serviceName: loki-headless`, `podManagementPolicy: Parallel` and the claim template `storage` (ReadWriteOnce, 20Gi). So the upgrade keeps claim `storage-loki-0`, and the orphan-and-rebind procedure of `k8s/README.md` is not necessary. The pod template changes:

- image `docker.io/grafana/loki:3.7.9`;
- `GOMEMLIMIT=1740MiB` and `GOGC=80` from the 2Gi memory limit, so the Go runtime collects garbage before the kernel stops the container;
- a liveness probe on `/loki/api/v1/status/buildinfo`, after ten failures at 30-second intervals;
- `seccompProfile: RuntimeDefault` on the pod and the container;
- the memberlist address from the pod IP, and the `/tmp` volume named `temp`.

The Loki configuration adds `ingester.wal.flush_on_shutdown: true`, the memberlist join and rejoin settings, and gRPC server limits. The HTTP read and write timeouts stay at 10 minutes. The Services `loki` and `loki-headless` add the gRPC ports 9095 and 9096. The NetworkPolicy of `logging` admits only port 3100 from outside the namespace, so those ports stay closed to other namespaces.

## The note of #1133

The note on `deletion_mode: disabled` records why Loki logs "deletion is not available for this tenant" on each query. The Loki v3.7.9 source holds the same code: `initQuerier` adds the cache generation middleware when the index is in object storage and retention is on, and `initCacheGenerationLoader` gives `NewGenNumberLoader` a client that is not wrapped per tenant. `gennumber_loader.go` did not change, and `GetCacheGenNumbers` still refuses a tenant with deletion off. The note now names v3.7.9 and its line numbers.

## Where the test lives

The issue asks for one test that holds the repository, the chart and the version of both paths. The two paths have two subjects, so two tests hold them, as `docs/TESTING.md` says:

- The Argo CD Application, its AppProject and the values are committed manifests. Their test is an invariant test, `test_loki_runs_the_grafana_community_chart_whose_loki_fixes_cve_2026_21729` in `tests/invariants/test_k8s_manifests.py`. It holds the repository, the chart and the version of the chart source, the AppProject that admits the repository, a `helm` block with the values file and no other value, no `loki.image` and no `singleBinary.image` in the values, and no `monitoring.selfMonitoring`.
- The `logging` stack of deploy-stack is behavior of devops-cli. Its test, `test_deploy_stack_installs_loki_from_the_grafana_community_chart`, joins `tests/test_k8s_logging_stack.py`, which already tests the `logging` stack. It holds the whole release and the repositories of the stack.

The two tests pin the same version, and `test_helm_sources_pinned_versions` in `tests/test_k8s_argocd_apps.py` holds that each Argo CD Helm Application and its deploy-stack release have the same version, chart and values file. The deploy-stack test reads `_HELM_RELEASES_BY_STACK` and `_HELM_REPOS_BY_STACK`, which no public interface shows: the dry run of `deploy-stack` names only the releases, and a run that is not a dry run needs patches of devops-cli names. The module already imported these names, so the test adds no new import of a private name. The retention settings that the issue names (`compactor.retention_enabled`, `retention_period: 720h`, `deletion_mode: disabled`) already have a test, `test_loki_deletes_logs_once_they_are_thirty_days_old` in `tests/test_k8s.py`.

`_loki_mode` in `tests/test_k8s_local_path_placement.py` said that the chart default is `SimpleScalable`. In the community chart the default is `Monolithic`, and `SingleBinary` is the old name of that mode. The check now takes both names, as the chart does.

## Rejected alternatives

- **Pin 18.17.1, the version that the issue names.** Rejected: 20.0.2 is newer, runs Loki 3.7.9, and its upgrade notes need no other change to these values (above).
- **Stay on `grafana/loki` and set `loki.image.tag` to 3.7.x.** Rejected: that chart is the Grafana Enterprise Logs chart. Its newest version, 7.5.0, ships Loki 3.6.16. The Loki upgrade guide says that the open-source chart moved to the community repository after chart 6.55.0, and the 7.x to 8.0.0 notes of the community chart send only Grafana Enterprise Logs users to `grafana/loki` (grafana/loki#20705). A Loki 3.7 image under a chart made for 3.6 has no upstream test.
- **Install the chart from the OCI registry `oci://ghcr.io/grafana-community/helm-charts/loki`.** Rejected: the AppProject already admits the HTTP repository, and the Grafana and Tempo Applications use it.
- **Admit Traefik in the NetworkPolicy of `logging`, so that `loki-ingress` reaches Loki.** Rejected: Loki runs with `auth_enabled: false`, so a Traefik peer opens the API without authentication (push, query and `detected_fields`) to each client that reaches Traefik. The policy stays closed, and #2439 deletes `loki-ingress`, whose backend the policy blocks.
- **Rename `deploymentMode: SingleBinary` to `Monolithic` and turn off `memcached.enabled` in this change.** Not done here: the chart accepts the old name and the render does not change, and a parallel change edits the same values file, so this change touches only the keys that the issue names. #2441 does it.
