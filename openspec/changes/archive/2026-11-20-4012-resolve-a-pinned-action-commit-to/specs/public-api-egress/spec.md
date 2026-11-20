## ADDED Requirements

### Requirement: The tags read of a pinned Action goes to api.github.com only
`devops research advisories` SHALL send the tags read of a pinned Action, `GET /repos/{owner}/{repo}/tags` (#4012), to `api.github.com` only, through the GitHub advisories client, at the public egress level and with the byte cap of that client. The approval of 2026-11-07 names the advisories API and not this path.

#### Scenario: The tags read of a commit pin
- **WHEN** `devops research advisories` resolves the pin `actions/checkout@<commit> # v4`
- **THEN** the tags read goes to `https://api.github.com/repos/actions/checkout/tags` and to no other host
