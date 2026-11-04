## ADDED Requirements

### Requirement: A stop on a read-only path is not retried
A stop whose text holds `Read-only file system` or `EROFS` SHALL have the class `read_only_path` and the action `wait`. It SHALL NOT have the class `ci_infra` or the action `retry`, and the rule `digest` SHALL NOT clear it on a new runner image.

#### Scenario: A read-only path error
- **WHEN** a command of the job stops with `OSError: [Errno 30] Read-only file system`
- **THEN** the class of the stop is `read_only_path` and the action left is `wait`

#### Scenario: A new runner image
- **WHEN** an item is Blocked with the class `read_only_path` and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`
