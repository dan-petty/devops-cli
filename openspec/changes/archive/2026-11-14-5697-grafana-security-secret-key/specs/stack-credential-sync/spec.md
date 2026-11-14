## ADDED Requirements

### Requirement: Secret monitoring/grafana-admin holds a secret-key entry
Secret `monitoring/grafana-admin` SHALL hold `secret-key` from keyring `grafana_secret_key`, generated with `token_urlsafe(32)` when the keyring holds no value. The Grafana values SHALL map `GF_SECURITY_SECRET_KEY` to this key via `envValueFrom`.

#### Scenario: Secret entry and Helm value mapping
- **WHEN** the cluster secret table and Grafana values are read
- **THEN** Secret `monitoring/grafana-admin` defines `secret-key` with generator `token_urlsafe(32)`
- **AND** `k8s/monitoring/grafana-values.yaml` maps `GF_SECURITY_SECRET_KEY` to `grafana-admin` `secret-key`
