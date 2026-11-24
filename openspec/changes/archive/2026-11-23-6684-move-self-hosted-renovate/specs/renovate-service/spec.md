## REMOVED Requirements

### Requirement: The timeouts nest inside the life of the token
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: Only the token init container reads Secret renovate
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: The pod meets Pod Security restricted with a read-only root
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: Renovate writes only to volumes, and the seed keeps the image files
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: The global config scopes Renovate to the App installation and onboards no repository yet
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: A post-upgrade task cannot open the installation token
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: The caches are on a kept claim, and Renovate opens update pull requests
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: The Renovate pod reaches only DNS, the collector and public HTTPS
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.

### Requirement: The CronJob runs Renovate every 2 hours, one run at a time
**Reason**: Self-hosted Renovate moved out of the product to homelab instance (#6684, dan-petty/homelab#95).
**Migration**: Run Renovate from the upstream chart in dan-petty/homelab#95.
