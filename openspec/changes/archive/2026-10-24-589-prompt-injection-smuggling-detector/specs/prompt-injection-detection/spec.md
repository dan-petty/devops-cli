# Spec Delta

## Purpose

Detects prompt-injection smuggling attacks, hidden Unicode payloads, delimiter injections, and canary token disclosures across files and text inputs.

## ADDED Requirements

### Requirement: Unicode Tag character smuggling detection
The system SHALL detect Unicode Tag block characters (`U+E0020` to `U+E007E`) carrying smuggled ASCII payloads and report them as INJ001 findings, exempting valid emoji tag sequences.

#### Scenario: Detecting hidden Tag-block ASCII payload
- **WHEN** injection scanning evaluates text containing characters in the range `U+E0020` to `U+E007E`
- **THEN** an INJ001 finding is produced with decoded ASCII payload

#### Scenario: Exempting valid emoji tag sequences
- **WHEN** injection scanning evaluates text containing an emoji tag sequence terminating with `U+E007F`
- **THEN** no INJ001 finding is reported for that sequence

### Requirement: Format-character and zero-width character smuggling detection
The system SHALL detect format-character runs and zero-width code points categorized as Unicode category `Cf` outside the Tag block and report them as INJ002 findings.

#### Scenario: Detecting zero-width spaces and format characters
- **WHEN** injection scanning evaluates text containing characters of category `Cf` such as `U+200B`, `U+200C`, `U+200D`, `U+2060`, or `U+FEFF`
- **THEN** an INJ002 finding is produced identifying the zero-width character occurrences

### Requirement: Chat template delimiter injection detection
The system SHALL detect privileged chat template delimiters in scanned text and report them as INJ003 findings.

#### Scenario: Detecting chat template markers
- **WHEN** injection scanning evaluates text containing delimiters such as `<|im_start|>`, `[INST]`, or `<<SYS>>`
- **THEN** an INJ003 finding is produced specifying the detected delimiter

### Requirement: Markdown data exfiltration link detection
The system SHALL detect markdown image or link references embedding data exfiltration query parameters and report them as INJ005 findings.

#### Scenario: Detecting markdown exfiltration query links
- **WHEN** injection scanning evaluates text containing markdown links with parameters such as `?leak=`, `?secret=`, or `?token=`
- **THEN** an INJ005 finding is produced identifying the exfiltration link

### Requirement: Cryptographic canary token auditing
The system SHALL generate high-entropy canary markers and audit response text for canary disclosure, reporting hits as EGR005 findings.

#### Scenario: Detecting canary leakage in response
- **WHEN** response auditing evaluates text containing an active canary token
- **THEN** an EGR005 finding is produced with critical severity

### Requirement: CLI scan injection command execution
The system SHALL provide a `devops scan injection` command that scans targets, applies suppression policies, generates SARIF reports, and enforces severity failure thresholds.

#### Scenario: Running scan injection with SARIF output
- **WHEN** `devops scan injection` is executed with `--sarif`
- **THEN** findings are written to the specified SARIF file with corresponding rule descriptors

#### Scenario: Failing on injection findings
- **WHEN** `devops scan injection` detects findings that match or exceed the `--fail-on` threshold
- **THEN** the command exits with non-zero status
