# Task: Tempo Runs Under the otel Namespace's Restricted Pod Security (#1627)

**Issue**: [#1627](https://github.com/dan-petty/devops-cli/issues/1627)
**Scope**: scope/k8s
**Feasibility**: Confirmed against the live cluster. The `tempo` StatefulSet failed to create `tempo-0` 343 times over 3 days 17 hours with `violates PodSecurity "restricted:latest"`, and its volume claim stayed Pending. A server-side dry run of the pod the fixed values render (`helm template` of chart 3.1.0, then `kubectl apply --dry-run=server` into `otel`) is admitted; the same dry run of the current values is refused with the same violation.

## Description
Tempo trace storage (#1135, v0.2.35) never ran. The `otel` namespace enforces PodSecurity `restricted` (`k8s/namespaces.yaml`), and `k8s/otel/tempo-values.yaml` set no seccomp profile on the pod and no container security context, so admission refused every pod the StatefulSet created. Argo CD reported the application as Progressing rather than Degraded, and Alertmanager has no receiver yet, so nothing surfaced it.

The values now set the controls `restricted` requires: the pod runs as the chart's non-root user with the `RuntimeDefault` seccomp profile, and the tempo container cannot escalate privileges, drops every capability and keeps a read-only root filesystem. Tempo writes only under the `/var/tempo` volume; the metrics generator, which would write under `/tmp/tempo`, stays disabled.

## Key Changes
- `k8s/otel/tempo-values.yaml`: top-level `securityContext` (non-root user, group and fsGroup 10001, `seccompProfile: RuntimeDefault`) and `tempo.securityContext` (`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`).
- `tests/test_k8s_tempo.py`: `test_tempo_pod_meets_the_otel_namespaces_restricted_pod_security` reads the namespace's enforce label and the values, and pins every restricted control and the disabled metrics generator.

## Acceptance Criteria
- [x] The values set every control PodSecurity `restricted` requires (`test_tempo_pod_meets_the_otel_namespaces_restricted_pod_security`).
- [x] The pod the values render is admitted by a server-side dry run into `otel`, and the previous values are refused.
- Pending a person: after the release reaches `main` and Argo CD syncs `tempo`, `kubectl -n otel get pod tempo-0` is Running and the `storage-tempo-0` claim is Bound.
