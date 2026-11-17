## MODIFIED Requirements

### Requirement: The GitHub notifier reads the keys of the secret push
The Argo CD Helm values SHALL define the notifier `service.github` with `appID: $github-appID`, `installationID: $github-installationID` and `privateKey: $github-privateKey`. Each `$key` that a notifier reads SHALL be a key of `argocd/argocd-notifications-secret` that the cluster secret push writes. The Cluster Secrets table of `k8s/README.md` SHALL list it. The values SHALL keep `notifications.secret.create: false`.

#### Scenario: The notifier keys match the push and the README
- **WHEN** a deploy of Application `devops` reaches the end of its sync on the cluster
- **THEN** the GitHub deployment of the sync shows on the repository, so `service.github` reads the three keys from the pushed Secret

### Requirement: Each notifier value is a string
Each value under `notifications.notifiers`, `notifications.triggers` and `notifications.templates` in `k8s/argocd/values.yaml` SHALL be a string. `ConfigMap.data` holds only strings, and the API server refuses a ConfigMap that holds a mapping.

#### Scenario: A notifier written as a mapping is found
- **WHEN** a value under `notifications.notifiers` is a YAML mapping
- **THEN** `uv run devops ci --check --only k8s` renders Application `argocd`, and the API server refuses the ConfigMap `argocd-notifications-cm` at the sync
