## ADDED Requirements

### Requirement: The spend itemizes token cost per tier
The implement job SHALL itemize the spend of every step under the tier that served it in `implement.spend`.

#### Scenario: Spend itemized per tier
- **WHEN** two steps ran on tier `devops-coder` and tier `devops-reasoning`
- **THEN** the record of the spend holds the token count for each tier and the aggregate total
