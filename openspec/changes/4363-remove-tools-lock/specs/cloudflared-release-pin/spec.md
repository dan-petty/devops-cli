## REMOVED Requirements

### Requirement: The tools lock installs a cloudflared release that rejects the compromised eMudhra intermediates
**Reason**: The tools lock and `devops install-tools` are gone (#4363). The devtools image installs cloudflared on a host.
**Migration**: The tag of Deployment `cloudflared` keeps its requirement, and the third-party image scan reports a finding in that image.
