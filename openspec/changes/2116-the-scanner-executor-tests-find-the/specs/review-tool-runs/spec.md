## ADDED Requirements

### Requirement: test-fixture-makes-scanner-findable-on-path
A test fixture that makes a review scanner findable SHALL place an executable stand-in file in a directory on PATH. It SHALL NOT patch a shutil or subprocess name.

#### Scenario: stand-in on PATH
- **WHEN** a test fixture makes a scanner binary findable for the tool executor
- **THEN** an executable file named after the scanner exists in a directory that is first on PATH, and no shutil.which or subprocess.run name is patched
