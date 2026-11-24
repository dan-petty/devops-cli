## ADDED Requirements

### Requirement: A version row counts every attempt and gives its infrastructure share
The report SHALL give each version with 10 attempts or more the count of all its attempts, infrastructure cuts included, and the share of the attempts that an infrastructure cut ended, beside the measure of the attempts with no cut.

#### Scenario: A version with an infrastructure cut
- **WHEN** the result lines of one version hold 12 attempts, and 3 of them ended with an infrastructure cut
- **THEN** the version row gives 12 all attempts, 3 infrastructure cuts and the share 0.25, beside the measure of 9 attempts
