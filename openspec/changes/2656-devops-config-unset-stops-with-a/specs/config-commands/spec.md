## ADDED Requirements

### Requirement: merge-key-unset-reports-clear-error
When the target key is present only through a YAML merge key, devops config unset SHALL exit with code 1 and print a message that names the file and states the key comes from a merge key. It SHALL NOT print a Python traceback.

#### Scenario: unset a merge-derived key
- **WHEN** the config file defines the key via <<: *anchor and the user runs devops config unset on that key
- **THEN** the command exits 1, prints a message naming the file and mentioning the merge key, and prints no Python traceback

### Requirement: direct-key-removal-is-unchanged
When the target key is directly present in the file, devops config unset SHALL remove the key and exit with code 0.

#### Scenario: unset a directly-present key
- **WHEN** the config file holds the key as a direct entry and the user runs devops config unset on that key
- **THEN** the key is removed from the file and the command exits 0
