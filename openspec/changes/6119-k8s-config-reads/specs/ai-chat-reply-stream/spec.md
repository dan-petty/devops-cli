## MODIFIED Requirements

### Requirement: The gateway keeps a streamed chat reply open
The gateway config SHALL set `litellm_settings.sse_keepalive_ping_interval_seconds` to a number of seconds that is more than 0 and less than 125, the Proxy Read Timeout of the Cloudflare edge.

#### Scenario: The gateway config
- **WHEN** a person streams a chat reply through the Cloudflare tunnel that waits more than 125 s for its first token
- **THEN** the reply is not cut at the edge, because the gateway writes a keepalive comment before 125 s pass
