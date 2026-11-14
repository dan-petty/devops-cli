# Proposal: #5697

## Why
Grafana Advisor reports that the security check for `secret_key` failed. In `k8s/monitoring/grafana-values.yaml`, Grafana runs without a configured `secret_key`, falling back to an insecure default key. Closes #5697.

## What Changes
Add entry `secret-key` to Secret `monitoring/grafana-admin` in `src/devops_cli/k8s/cluster_secrets.py`. Map `GF_SECURITY_SECRET_KEY` in `k8s/monitoring/grafana-values.yaml` to Secret `grafana-admin` key `secret-key`. Update `k8s/README.md` and cluster secret tests.

## Capabilities
- `stack-credential-sync`

## Impact
Grafana reads a unique, secure secret key from Secret `grafana-admin` at startup, resolving the security finding without affecting anonymous datasources.

## Feasibility
Grafana documentation and the Grafana Helm chart support setting `GF_SECURITY_SECRET_KEY` via `envValueFrom`. The secret table in `src/devops_cli/k8s/cluster_secrets.py` already manages `monitoring/grafana-admin`. The change fits one pull request.

## Existing Tool Considered
Grafana's native environment variable `GF_SECURITY_SECRET_KEY` and the cluster secret management subsystem (`devops k8s push-secrets`) provide this capability.
