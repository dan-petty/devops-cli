## MODIFIED Requirements

### Requirement: Alloy reaches the metrics port of each component
The egress of the NetworkPolicies of namespace `monitoring` SHALL let the `alloy-metrics` pod send to namespace `object-store` on the metrics port of each component, and the perimeter of the store SHALL admit the pod on that port.

#### Scenario: The committed perimeters
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/monitoring` and `k8s/object-store`
- **THEN** the row passes with an egress rule of `monitoring-default-perimeter-egress` to namespace `object-store` on 9327 and an ingress rule of the store from namespace `monitoring` on 9327

#### Scenario: A monitoring perimeter with no egress to the store
- **WHEN** `uv run devops ci --check --only k8s` runs the scrape rule on the monitoring policies with the egress rule to `object-store` removed
- **THEN** the rule reports a problem that names `monitoring-default-perimeter-egress`

### Requirement: Only the worker reaches the admin gRPC port
The NetworkPolicies of namespace `object-store` SHALL admit to the admin pod on TCP 33646 only the worker pods, and SHALL let only the worker pods send to it. No egress rule of these policies SHALL cover the port for another pod, also with no `ports`, so that the port stays closed if a policy gets both types again: the policy controller of the cluster does not apply the ingress rules of a policy with both types to traffic that an egress rule of that policy allows. A policy selects only pods of its namespace, so the ingress rules hold for other namespaces.

#### Scenario: The committed perimeter
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes, a filer pod, the operator pod and a pod of another namespace get no ingress rule to 33646 of the admin pod, no pod of the namespace other than the worker gets an egress rule to it, and the worker gets both

#### Scenario: A perimeter that admits a filer
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on a fixture policy that admits the filer pods on 33646
- **THEN** the rule reports a problem that names the policy and port 33646

#### Scenario: A perimeter whose in-namespace egress has no ports
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on the committed policies with no `ports` in the in-namespace egress rule of `object-store-perimeter-egress`
- **THEN** the rule reports a problem that names `object-store-perimeter-egress` and port 33646

#### Scenario: A policy that lets a filer send to the admin port
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on a fixture policy that lets the filer pods send to the admin pod on 33646
- **THEN** the rule reports a problem that names the policy and port 33646

#### Scenario: A worker with no egress to the admin port
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on the committed policies without `object-store-worker`
- **THEN** the rule reports that no policy lets the worker send to the admin pod on 33646

#### Scenario: The live port
- **WHEN** a person runs `nc -z -w 3 seaweedfs-admin 33646` in a filer pod and in the worker pod
- **THEN** the filer pod cannot connect and the worker pod connects
