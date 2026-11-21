## ADDED Requirements

### Requirement: The replay keeps the addopts of the tree
The pytest run of the replay SHALL keep the `addopts` of the tree that it runs in, and SHALL start no xdist worker. A test that reads `addopts` SHALL pass in the replay when it passes in a normal run.

#### Scenario: A test reads addopts in the replay
- **WHEN** the replay runs a test that reads `addopts` and the number of xdist workers, in a project whose `addopts` give `-n 2`
- **THEN** the test reads the `addopts` of the project and 0 workers, and the JUnit report of the replay gives it as passed
