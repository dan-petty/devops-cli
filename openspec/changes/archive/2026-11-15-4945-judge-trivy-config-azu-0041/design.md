# Design

## Decisions

- **Clear AZU-0041 using `api_server_access_profile.authorized_ip_ranges`:** The owner decision of 2026-11-12 scopes the fix to setting authorized IP ranges on the AKS API server access profile.
- **Variable with no default value:** Declare `api_server_authorized_ip_ranges` in `tf/azure/variables.tf` without a default value. This prevents committing any IP addresses or CIDR literals to git, complying with SECURITY.md rule 8.
- **Leave `network_profile` unchanged:** AZU-0043 relates to network policy, which issue #4949 tracks. `network_profile` remains untouched.

## Rejected alternatives

- **Set `network_policy = "azure"` in `network_profile`:** Rejected because this clears AZU-0043 (tracked in #4949) rather than AZU-0041. A previous PR (#5053) was closed because it incorrectly targeted AZU-0043.
- **Add a `.trivyignore.yaml` suppression entry:** Rejected because SECURITY.md forbids an agent from ignoring a CRITICAL security alert when a direct fix is available.
- **Configure a private cluster:** Rejected because the owner constraint specifies keeping the API server endpoint public while restricting access by authorized IP ranges.
- **Provide a default RFC 5737 IP block in `variables.tf`:** Rejected because the owner decision specifies no default value, forcing explicit configuration at deployment time.
