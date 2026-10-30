# Spec Delta

## ADDED Requirements

### Requirement: Intake links a candidate filed from --source as a sub-issue
When intake files a candidate whose `--source` links an issue of the same repository, intake SHALL add the filed issue as a sub-issue of that issue.

#### Scenario: Candidate filed with --source linking an issue in the same repository
- **WHEN** intake files a candidate whose `--source` links an issue in the same repository
- **THEN** intake adds the filed issue as a sub-issue of that issue, and lists the write in the dry-run plan
