## ADDED Requirements

### Requirement: The brain holds no entry of a number that is no issue of the repository
When GitHub answers a read of a number with status 404 or with an answer that names another issue, `GitHubRoadmapStore` SHALL remove the brain entry of that number and SHALL write no entry for the answer. The store SHALL send the removal only for a repository whose entries the shared tier takes from the process.

#### Scenario: A conditional read that answers with another issue
- **WHEN** the `valkey_server` fake holds an entry of issue 7 of `acme/widgets` that is older than one hour, and the fake GitHub answers the read with `If-None-Match` with status 200 and a payload whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `issue(7)` returns None, and the `valkey_server` fake holds no entry of issue 7 and no entry of issue 12 of `acme/widgets`

### Requirement: The store uses an entry only for the issue that it names
The store SHALL use a brain entry only when its record names the requested number and the repository of the store. It SHALL remove any other entry and read the issue from GitHub.

#### Scenario: An entry whose record names another issue
- **WHEN** the `valkey_server` fake holds, under issue 12 of `acme/widgets`, a fresh entry whose record names issue 12 of `acme/other`, and the fake GitHub answers the read of `repos/acme/widgets/issues/12` with issue 12 of `acme/widgets`
- **THEN** `issue(12)` sends one read to the fake GitHub and returns its issue, and the entry that the fake holds names `acme/widgets`

#### Scenario: A 304 answer gives the entry of the requested issue
- **WHEN** the `valkey_server` fake holds an entry of issue 7 of `acme/widgets` that is older than one hour, and the fake GitHub answers the read with `If-None-Match` with status 304
- **THEN** `issue(7)` returns the record of the entry
