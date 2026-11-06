## ADDED Requirements

### Requirement: The copy of a volume move keeps its source open until the destination has ended
The source side of the copy SHALL run `cat` after GNU tar succeeds, and a named pipe SHALL join the stdout of the destination side to the stdin of the source side. So the stdout of the source stays open until the destination has ended, and a slower destination loses no data. Bash SHALL make the named pipe and remove it on exit.

#### Scenario: The source holds until the destination ended
- **WHEN** a move runs its copy
- **THEN** the source side runs `tar -C /src --numeric-owner --sparse -cpf - . && exec cat` with `kubectl exec -i`, and reads its stdin from the named pipe
- **AND** the destination side writes its stdout to the same named pipe
