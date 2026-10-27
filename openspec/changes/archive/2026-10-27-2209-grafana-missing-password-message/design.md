# Design

`_report_credential_sync` prints one line for each credential. A `missing` outcome of `grafana` now prints `MESSAGES.k8s.grafana_password_missing`. The other `missing` outcomes keep the cluster message.

## Rejected alternatives

- **Add a source field to `CredentialSync`.** Only one credential has a keyring source, so a field adds a type change for one message. Rejected.
- **Change the generic message to name both places.** The Argo CD message is correct, and a vague message helps no reader. Rejected.
