## ADDED Requirements

### Requirement: The osv-scanner inventory names no tool version
The CycloneDX inventory of the osv-scanner adapter SHALL name the tool with `vendor` and `name` only. It SHALL NOT have the optional `version` field, because the adapter reads no version of the scanner that ran.

#### Scenario: The tool entry has no version
- **WHEN** a test parses an osv-scanner report with `parse_osv_scanner_output`
- **THEN** `metadata.tools` of the inventory is one entry with `vendor` `Google` and `name` `osv-scanner`, and the entry has no `version` key
