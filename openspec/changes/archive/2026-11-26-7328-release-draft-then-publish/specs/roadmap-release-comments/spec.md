## MODIFIED Requirements

### Requirement: The row takes the releases of the last 12 hours
The row SHALL read the 30 newest releases and take those that are published within 12 hours of the round and are neither a draft nor a prerelease. A release outside that window SHALL get no comment, and the ledger SHALL drop its entry. A draft with no publication time SHALL get no comment and SHALL stop no comment of another release.

#### Scenario: Old, draft and prerelease
- **WHEN** the list holds a release of 13 hours ago, a draft and a prerelease
- **THEN** the row reads no pull request for them and posts no comment

#### Scenario: A draft with no publication time
- **WHEN** the list holds a draft whose `published_at` is null and a release `v1.0.0` of 2 hours ago
- **THEN** each closed issue of `v1.0.0` gets its comment, the draft gets none, and the ledger holds no entry for the draft
