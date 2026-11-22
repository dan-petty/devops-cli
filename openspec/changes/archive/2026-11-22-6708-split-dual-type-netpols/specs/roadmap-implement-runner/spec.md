## MODIFIED Requirements

### Requirement: Only the Service pod may reach the API server
A NetworkPolicy SHALL admit egress of the pods labeled `app.kubernetes.io/name=roadmap-service` to TCP 6443 through an `ipBlock` that excludes `169.254.169.254/32`. No policy SHALL admit a Job pod to port 6443. The Job pods SHALL keep the egress of `devops-default-perimeter-egress`: DNS, the gateway on 4000, the cache on 6379, the OTLP collector on 4318 and public HTTPS.

#### Scenario: The policies are read
- **WHEN** a test reads the rendered NetworkPolicies of namespace `devops`
- **THEN** the policy for `roadmap-service` holds one egress rule, to port 6443 with the metadata address excluded, and no other policy of the namespace names port 6443

### Requirement: Public HTTPS excludes the non-public ranges
The public HTTPS rule of `devops-default-perimeter-egress` SHALL exclude the private ranges, the shared address space `100.64.0.0/10`, the link-local range `169.254.0.0/16`, `169.254.169.254/32`, `192.0.0.0/24` and `198.18.0.0/15`.

#### Scenario: The policy is read
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and a person reads NetworkPolicy `devops-default-perimeter-egress` of the render
- **THEN** the `except` list of the port 443 rule holds exactly those ranges
