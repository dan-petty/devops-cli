## ADDED Requirements

### Requirement: The profile hashes the versions of the tools that ran
The review profile SHALL hold `tool_versions_digest`, the digest of the tool, the version and the binary digest of each tool run of the review. It SHALL be empty when no tool ran. It SHALL read no `tools.lock`.

#### Scenario: Another installed Semgrep
- **WHEN** a test builds a profile with a run of Semgrep `1.0.0`, again with the same run, and with a run of Semgrep `1.1.0`
- **THEN** the first two digests are equal, the third differs, and a profile with no run has an empty digest
