## ADDED Requirements

### Requirement: The record of a run names the network of the tool
The record of each run SHALL name, in `network`, the network that the tool had: `host` for the direct executor, `none` for the sandbox executor with no network profile, and the name of the profile, `kube-api`, for the sandbox executor with that profile.

#### Scenario: The network of each kind of run
- **WHEN** the direct executor runs a request, and the sandbox executor runs a request with no network profile and a Popeye request with the profile `kube-api`
- **THEN** the records name the network `host`, `none` and `kube-api`
