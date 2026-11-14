# implement-job-label-guard Specification

## Purpose
Check that the item label of a runner Job matches the recording item before the Service reports the Job. This check prevents log disclosure.

## Requirements

### Requirement: Skip a Job of another item
The implement round SHALL check the item label of a held runner Job against the item that records the Job before it reads the log or writes a comment or state.

#### Scenario: Record names another item's Job
- **WHEN** Item A records the name of an ended runner Job whose item label names item B
- **THEN** The round posts no comment on A, reads no log of that Job and records no `implement.job_state` on A.

### Requirement: Report a Job of the recording item
The implement round SHALL report an ended runner Job whose item label names the item that records it.

#### Scenario: Record names its own Job
- **WHEN** Item A records the name of an ended runner Job whose item label names A
- **THEN** The round posts the usual report comment on A and records `implement.job_state` on A.
