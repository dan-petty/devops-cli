## REMOVED Requirements

### Requirement: Open WebUI allows only the origins of its Ingress hosts
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Argo CD applies three homelab Applications server-side
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: An Ingress with a placeholder host fires an alert
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.
