## REMOVED Requirements

### Requirement: Grafana pins each Drilldown app at its release for Grafana 13
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Renovate reads each Grafana plugin pin
**Reason**: `.github/renovate.json` holds no Grafana plugin manager, because the values file that it read is in the environment repository (#7290).
**Migration**: Renovate of the environment repository updates the pins.

### Requirement: Each plugin update is its own pull request below the next major
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Grafana preinstalls the LLM app plugin
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Grafana provisions grafana-llm-app for LiteLLM gateway
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Grafana enables the dashgpt feature toggle
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.
