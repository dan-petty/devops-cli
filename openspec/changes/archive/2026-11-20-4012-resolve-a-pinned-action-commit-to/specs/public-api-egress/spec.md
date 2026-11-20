## MODIFIED Requirements

### Requirement: The research agent may send requests to api.github.com and www.cisa.gov
The owner approved, on 2026-11-07, the egress of the research agent to `api.github.com` (the advisories API and the tags API) and to `www.cisa.gov` (the Known Exploited Vulnerabilities list). The approval has the public egress level and a byte cap on each reply. `devops research advisories` SHALL send a request to these two hosts only, and its clients SHALL send no contact data in any header.

#### Scenario: The hosts of a run
- **WHEN** `devops research advisories` runs on a repository with a GitHub Action, a mapped chart and a finding with a CVE, and no Python or Node package
- **THEN** the requests go to `api.github.com` and `www.cisa.gov` only
