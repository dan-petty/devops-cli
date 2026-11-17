## REMOVED Requirements

### Requirement: The Service keeps Recreate until its Lease code runs
**Reason**: Release 0.170.0 carries the Lease code of #6058, and the running pod holds the Lease `roadmap-service-rows`, so the Service rolls with a surge release (#6107).
**Migration**: The requirement "The Service rolls with a surge release" holds the strategy, and the requirement "One pod of the Service holds the rows" keeps the rows to one pod.

## ADDED Requirements

### Requirement: The Service rolls with a surge release
`deployment/roadmap-service` SHALL set `replicas: 1` and `RollingUpdate` with `maxSurge: 1` and `maxUnavailable: 0`, so the old pod gets SIGTERM only after the new pod passes `/readyz`. The new pod SHALL run on the node of the home volume and mount its ReadWriteOnce claim beside the old pod. The readiness of a pod SHALL NOT wait for the Lease `roadmap-service-rows`.

#### Scenario: The manifest checks
- **WHEN** `uv run devops ci --check --only k8s,kube-linter` runs
- **THEN** both rows pass, and the `kube-linter` row checks `deployment/roadmap-service` with `no-rolling-update-strategy` and `no-readiness-probe`, with no exception annotation

#### Scenario: A release of the Service
- **WHEN** a release replaces the pod, and a person runs `kubectl -n devops rollout status deployment/roadmap-service` and `kubectl -n devops get pods -l app.kubernetes.io/name=roadmap-service -w`
- **THEN** the rollout completes, the new pod is `Ready` before the old pod stops, `kubectl -n devops get lease roadmap-service-rows -o jsonpath='{.spec.holderIdentity}'` names the new pod only after the drain of the old pod ends, and `uv run devops gh api 'repos/<owner>/<repo>/hooks/<id>/deliveries?per_page=100' --jq '[.[] | select(.delivered_at >= "<start of the release>" and .status_code >= 500)] | length'` prints `0`
