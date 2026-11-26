## REMOVED Requirements

### Requirement: The tunnel Deployment runs a cloudflared release that rejects the compromised eMudhra intermediates
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The scan of the cloudflared image only reports
**Reason**: `third-party-image-scan.yml` has no `cloudflared` matrix entry, because the Deployment that it read is in the environment repository (#7290).
**Migration**: The environment repository scans the image of its tunnel.
