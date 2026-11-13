## ADDED Requirements

### Requirement: A gateway rollout lets the old pod finish its open calls
The gateway pod SHALL set `terminationGracePeriodSeconds` to 600, which is shorter than the router timeout of the gateway config. The gateway Deployment SHALL use a rolling update, so the new pod starts before the old pod stops.

#### Scenario: The rendered gateway pod waits 600 s for its open calls
- **WHEN** Kustomize renders `k8s/llm`
- **THEN** the pod template of Deployment `llm-gateway` sets `terminationGracePeriodSeconds: 600`
- **AND** 600 is less than `router_settings.timeout` of `k8s/llm/gateway/config.yaml`
- **AND** the Deployment sets no strategy other than `RollingUpdate`

### Requirement: A restart of the gateway database waits 15 s for open sessions
The CloudNativePG Cluster `llm-gateway-db` SHALL set `smartShutdownTimeout` to 15, which is less than its `stopDelay`.

#### Scenario: The Cluster limits the smart shutdown to 15 s
- **WHEN** the check reads the Cluster of `k8s/llm/gateway-db.yaml`
- **THEN** it sets `smartShutdownTimeout: 15`
- **AND** 15 is less than its `stopDelay`, or less than 1800 when it sets none

### Requirement: One slow request does not fail a probe of the gateway
The startup, liveness and readiness probes of the gateway container SHALL each set `timeoutSeconds` to 5, which is shorter than the period of the probe.

#### Scenario: Each probe of the rendered gateway waits 5 s
- **WHEN** Kustomize renders `k8s/llm`
- **THEN** the `startupProbe`, `livenessProbe` and `readinessProbe` of the gateway container each set `timeoutSeconds: 5`
- **AND** each timeout is less than the `periodSeconds` of its probe
