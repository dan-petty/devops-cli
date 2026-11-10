## ADDED Requirements

### Requirement: osv-scanner reports unavailable when its binary is not on PATH
The osv-scanner adapter SHALL verify the presence of the `osv-scanner` binary before executing a scan over lockfiles. When `osv-scanner` is not available on PATH, the adapter SHALL NOT start the process and SHALL return the outcome `unavailable` with no findings.

#### Scenario: osv-scanner binary is missing from PATH
- **WHEN** the osv-scanner adapter scans a tree with lockfiles and no directory of PATH holds `osv-scanner`
- **THEN** the scan does not start, and the outcome is `unavailable` with no findings
