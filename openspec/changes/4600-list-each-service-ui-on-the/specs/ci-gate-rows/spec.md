## ADDED Requirements

### Requirement: The k8s row refuses a start-page opt-in on a machine endpoint
The `k8s` row of `devops ci` SHALL apply the start page rule to every Ingress, IngressRoute and Mattermost object of the product base. It SHALL fail each object that neither opts in with the seven start-page annotations nor appears on the machine-endpoint list, and each machine endpoint that carries a `gethomepage.dev` annotation.

#### Scenario: A machine endpoint that opts in
- **WHEN** The webhook Ingress of the roadmap Service carries `gethomepage.dev/enabled` and `uv run devops ci --check --only k8s` runs
- **THEN** The row exits non-zero and names the namespace `devops` and the name `roadmap-service`

#### Scenario: A machine endpoint with no tile
- **WHEN** The product base applies the webhook Ingress of the roadmap Service with no start-page annotation and `uv run devops ci --check --only k8s` runs
- **THEN** The row exits 0 and reports no finding

#### Scenario: An object with neither opt-in nor machine-endpoint status
- **WHEN** An Ingress outside the machine-endpoint list carries no `gethomepage.dev` annotation and `uv run devops ci --check --only k8s` runs
- **THEN** The row exits non-zero and names the namespace and name of the Ingress

#### Scenario: An incomplete opt-in
- **WHEN** A routing object of the render carries `gethomepage.dev/enabled` and no `gethomepage.dev/group`, and `start_page_problems` reads it
- **THEN** It returns one finding that names the missing `gethomepage.dev/group` annotation

### Requirement: The k8s row accepts only a known group and a routed link host
The `k8s` row SHALL accept a start-page `group` only from `AI`, `Observability`, `Platform`, `Source Control` and `Collaboration`. It SHALL accept an `href` only as an `https://` link whose host uses `{{HOMEPAGE_VAR_DOMAIN}}` and matches a routed host when read as `example.com`, and SHALL count each kind, namespace and name once.

#### Scenario: An unknown group
- **WHEN** An opted-in routing object sets `gethomepage.dev/group` to `Cluster`, and `start_page_problems` reads it
- **THEN** It returns one finding that names `Cluster` and the five accepted groups

#### Scenario: A link without the domain placeholder
- **WHEN** An opted-in Ingress sets `gethomepage.dev/href` to `https://hooks.example.com/` with literal `example.com` instead of `{{HOMEPAGE_VAR_DOMAIN}}`, and `start_page_problems` reads it
- **THEN** It returns one finding that names `{{HOMEPAGE_VAR_DOMAIN}}`

#### Scenario: A link on a host that the object does not route
- **WHEN** An opted-in Ingress sets `gethomepage.dev/href` to `https://grafana.{{HOMEPAGE_VAR_DOMAIN}}/` and its rules hold only the host `hooks.example.com`, and `start_page_problems` reads it
- **THEN** It returns one finding that names the link host and the routed host

#### Scenario: One object counted once
- **WHEN** The render holds the same Ingress twice, with the same namespace and name, and `start_page_problems` reads it
- **THEN** It returns one finding for that object, not two
