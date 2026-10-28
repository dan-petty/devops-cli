## ADDED Requirements

### Requirement: The Grafana, Prometheus and Argo CD clients dial at the configured level
The `devops grafana`, `devops prometheus` and `devops argo cd apps` commands, the Argo CD fleet sync, the Argo CD GitOps sync, the rollout metric gate, and the Argo CD and Grafana token calls SHALL dial loopback and public addresses. They SHALL dial private addresses only when `ai.allow_private_network` is true.

#### Scenario: A configured client without the flag
- **WHEN** `ai.allow_private_network` is false, and the host of `grafana.url`, `prometheus.url` or `argocd.url` answers `127.0.0.1` and then `10.0.0.1`
- **THEN** the client dials `127.0.0.1` and refuses `10.0.0.1` with no dial

#### Scenario: A configured client with the flag
- **WHEN** `ai.allow_private_network` is true, and the host of one of these URLs answers `127.0.0.1` and then `10.0.0.1`
- **THEN** the client dials both addresses

### Requirement: A command that gets a refused address prints the refusal
A `devops grafana`, `devops prometheus` or `devops argo cd apps sync` command that gets an address that its level refuses SHALL print the refusal without a traceback. It SHALL exit with status 2, the status of `SSRF_BLOCKED`. `devops grafana dashboards sync` SHALL stop at the first refused file.

#### Scenario: A private Prometheus address without the flag
- **WHEN** `ai.allow_private_network` is false, the host of `prometheus.url` answers `10.0.0.1`, and `devops prometheus query up` runs
- **THEN** the command exits with status 2 and prints the refusal, with no dial

#### Scenario: A private Grafana address in the dashboard sync
- **WHEN** `ai.allow_private_network` is false, the host of `grafana.url` answers `10.0.0.1`, and `devops grafana dashboards sync` runs on a directory with two dashboard files
- **THEN** the command prints the refusal one time and exits with status 2, with no dial

### Requirement: A failed Argo CD token mint ends the command with its cause
A `devops argo cd apps` command that mints an Argo CD token before its request SHALL print a failed mint with its cause, without a traceback, and SHALL exit with status 1, the status of a failed credential step. A refused address is such a cause.

#### Scenario: A private Argo CD address in the token mint
- **WHEN** `ai.allow_private_network` is false, the host of `argocd.url` answers `10.0.0.1`, the Argo CD admin password is set, no Argo CD token is stored, and `devops argo cd apps list`, `sync` or `status` runs
- **THEN** the command exits with status 1 and prints the failed token mint with the refusal, with no dial

### Requirement: The Grafana, Prometheus and Argo CD clients dial the address that they checked
Each client that the requirement "The Grafana, Prometheus and Argo CD clients dial at the configured level" names SHALL resolve the host one time, at the connect, and SHALL give the socket the address that it checked, never the host name. Each one SHALL refuse cloud metadata addresses.

#### Scenario: A host that answers differently at a later lookup
- **WHEN** the host of `grafana.url`, `prometheus.url` or `argocd.url` answers a public address at the first lookup and `169.254.169.254` at each later lookup
- **THEN** the socket gets neither the host name nor `169.254.169.254`

### Requirement: A service URL that is not HTTP stops the command before a request
The `devops grafana`, `devops prometheus` and `devops argo cd apps` commands SHALL exit with status 1 and an error that names the setting, without a traceback, when `grafana.url`, `prometheus.url` or `argocd.url` does not have the `http` or `https` scheme and a host. They SHALL make no lookup and send no request, also no token mint.

#### Scenario: A k8s address in prometheus.url
- **WHEN** `prometheus.url` is `k8s://monitoring/prometheus-server:9090` and `devops prometheus query up` runs
- **THEN** the command exits with status 1, the error names `prometheus.url`, and no lookup or dial occurs

#### Scenario: A k8s address in argocd.url with the admin password
- **WHEN** `argocd.url` is `k8s://argocd/argocd-server:80`, the Argo CD admin password is set, no Argo CD token is stored, and `devops argo cd apps list`, `sync` or `status` runs
- **THEN** the command exits with status 1, the error names `argocd.url`, and no lookup or dial occurs
