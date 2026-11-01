## ADDED Requirements

### Requirement: redundant-test-file-elimination
The test suite SHALL contain no test file that kills no unique mutant of the source lines it covers, as determined by mutation testing with the full suite and with the file excluded.

#### Scenario: file with no unique mutant is removed
- **WHEN** a test file in the review or scanner suite kills no mutant that the rest of the suite leaves alive
- **THEN** the file is deleted or its distinct case is moved into the file that covers the same lines

#### Scenario: file with a unique mutant is kept
- **WHEN** a test file kills at least one mutant that survives only when the file is excluded
- **THEN** the file remains in the suite and the pull request names the mutant

#### Scenario: contract and invariant tests are preserved
- **WHEN** a test file matches test_architectural_invariants, test_contract, or a security-guard test name
- **THEN** the file is not deleted by this change
