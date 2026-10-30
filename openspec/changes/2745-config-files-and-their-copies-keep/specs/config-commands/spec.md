## ADDED Requirements

### Requirement: Preserve existing file mode on write
A write of a config file that already exists MUST preserve the mode of the existing file.

#### Scenario: Write to a 0600 file
- **WHEN** A config file with mode 0600 is written by devops config set or devops config unset
- **THEN** The resulting file has mode 0600

### Requirement: New config file gets mode 0600
A config file that does not exist and is created by a write MUST be created with mode 0600.

#### Scenario: Create a new config file
- **WHEN** A write creates a config file that did not exist before
- **THEN** The new file has mode 0600

### Requirement: Backup copy keeps source mode
A backup copy of a config file MUST have the same mode as the source file.

#### Scenario: Copy a 0600 file
- **WHEN** A backup copy is made of a config file with mode 0600
- **THEN** The copy has mode 0600

### Requirement: Temporary file never more open than source
A temporary file written during a config write MUST have a mode no more open than the file it replaces, or 0600 when no file exists.

#### Scenario: Tmp file mode during redact copy
- **WHEN** A temporary file is created during a redacted copy of a config file with mode 0600
- **THEN** The temporary file has mode 0600 before it is replaced by os.replace
