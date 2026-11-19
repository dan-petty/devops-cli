## ADDED Requirements

### Requirement: Each host of the together run is one term of the limit
The limit of the run of the hosts with no disruptive class SHALL name each host and the offline exclusion as separate comma-separated terms, so the run reaches every host of the plan and no host of the group of hosts out of service.

#### Scenario: A together run of two hosts
- **WHEN** a plan holds node-1 and node-4 with no disruptive class and the offline group is `offline`
- **THEN** the limit of their run is `node-1.example.com,node-4.example.com,!offline`

#### Scenario: The dry run shows each together host as its own term
- **WHEN** a dry run of the apply command reads a plan whose together run holds node-1 and node-4
- **THEN** the request plan shows `node-1.example.com,node-4.example.com,!<offline group>`
