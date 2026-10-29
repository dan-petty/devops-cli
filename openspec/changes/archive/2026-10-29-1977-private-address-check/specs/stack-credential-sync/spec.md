## MODIFIED Requirements

### Requirement: The token check and the mint dial at the configured level
The token check and the mint of Argo CD and Grafana SHALL dial loopback and public addresses, and private addresses only when `ai.allow_private_network` is true. This SHALL apply in `devops k8s sync-secrets` and in the commands that mint a missing token. An address that the level refuses SHALL make the check or the mint fail with a cause that names the refusal, as a request error does.

#### Scenario: A private Grafana address without the flag
- **WHEN** `ai.allow_private_network` is false, the keyring holds a Grafana token, the host of `grafana.url` answers `192.0.2.10`, and the sync runs
- **THEN** the sync reports `grafana_token` as `failed` with a cause that names the refusal, no dial occurs, and the stored token stays in the keyring

#### Scenario: A private Grafana address with the flag
- **WHEN** `ai.allow_private_network` is true, the keyring holds a Grafana token, the host of `grafana.url` answers `192.0.2.10`, and the sync runs
- **THEN** the check dials `192.0.2.10`
