## REMOVED Requirements

### Requirement: The memory limits have room above the measured peak
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The exporter CPU limits do not throttle a scrape
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The 16 GiB Ollama tier limits its memory to its request
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The Tempo query limits stay under the memory limit
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The rendered Tempo configuration parses with the Tempo image of the chart
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.
