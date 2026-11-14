# Design

## Decisions
- Add `secret-key` to Secret `monitoring/grafana-admin` using generator `token_urlsafe(32)` and keyring entry `grafana_secret_key`.
- Configure `envValueFrom.GF_SECURITY_SECRET_KEY` in `k8s/monitoring/grafana-values.yaml`.

## Rejected alternatives
- Plaintext `secret_key` in `grafana.ini`: Rejected because committing secrets or static tokens to git violates repository security rules.
- Separate Secret `grafana-security`: Rejected because `grafana-admin` already manages Grafana credentials and restarts the pod on changes.
