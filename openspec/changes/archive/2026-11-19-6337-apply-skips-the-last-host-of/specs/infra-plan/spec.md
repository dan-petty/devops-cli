## MODIFIED Requirements

### Requirement: No host of the offline group is in the limit
The host pattern of the run SHALL be the `--limit`, else `all`, followed by `!<offline group>` as a term of its own when the profile names a group of hosts out of service: the term is joined with a comma when the limit holds a comma, and with a colon when it holds none.

#### Scenario: A limit that names an offline host
- **WHEN** the limit is `node-5.example.com` and the offline group is `offline`
- **THEN** the host pattern is `node-5.example.com:!offline`

#### Scenario: A comma limit names each host and the offline group as its own term
- **WHEN** the limit is `node-1.example.com,node-2.example.com` and the offline group is `offline`
- **THEN** the host pattern is `node-1.example.com,node-2.example.com,!offline`

#### Scenario: The dry run shows the pattern of a comma limit
- **WHEN** a dry run of the plan command names the limit `node-1.example.com,node-2.example.com` and the offline group `offline`
- **THEN** the request plan shows the limit `node-1.example.com,node-2.example.com,!<offline group>`
