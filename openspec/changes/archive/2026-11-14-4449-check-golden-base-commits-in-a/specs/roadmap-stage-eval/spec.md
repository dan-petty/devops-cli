## MODIFIED Requirements

### Requirement: Each commit of the set is a real commit or the case reads none
The `roadmap-stage-eval-commits` row of `devops ci` SHALL check the `base_commit` of each case of the golden set: it SHALL be the full hash of a commit of this repository, or `NO_COMMIT` in a case whose notes say that it reads no commit. The test of the golden set SHALL check that the `merge_commit` of each case is a full hash or `NO_COMMIT`, and that a case names both commits or neither.

#### Scenario: The commits of the set
- **WHEN** the `roadmap-stage-eval-commits` row reads the cases
- **THEN** each base commit that is not `NO_COMMIT` has 40 hexadecimal characters and names a commit of this repository, and each case with `NO_COMMIT` has a note that says it reads no commit

#### Scenario: The merge commit of each case
- **WHEN** the test of the golden set reads the cases
- **THEN** each merge commit is a full hash or `NO_COMMIT`, and a case names both commits or neither
