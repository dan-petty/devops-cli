## ADDED Requirements

### Requirement: A SearXNG update waits for an approval in its own branch
The Renovate configuration SHALL give each update of the SearXNG image the group `searxng` and SHALL hold it for an approval on the Dependency Dashboard, so that the update comes in its own pull request and the other container images do not wait for it.

#### Scenario: A new SearXNG tag
- **WHEN** Renovate finds a new tag of `docker.io/searxng/searxng`
- **THEN** the Dependency Dashboard lists the update for approval, and after the approval Renovate opens it on a `searxng` branch, apart from `container images`
