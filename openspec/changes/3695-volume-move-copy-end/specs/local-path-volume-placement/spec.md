## MODIFIED Requirements

### Requirement: A volume move copies the data and compares the two sides
The run SHALL make the claim `<claim>-move` and the pod `<claim>-dst` on the target node, scale the workloads to zero, start the pod `<claim>-src` with the old claim read-only, and copy with GNU tar over two `kubectl exec` streams joined by `bash -o pipefail`. The source side SHALL keep its stdout open until the destination side has ended: a named pipe SHALL join the stdout of the destination side to the stdin of the source side, and after GNU tar succeeds the source side SHALL run `cat`. When the copy fails, it SHALL empty `/dst` and copy one more time. It SHALL compare the entries, the files, the bytes of regular files, a metadata digest and a content digest of the two sides.

#### Scenario: A dropped copy
- **WHEN** the first copy fails with `connection reset by peer`
- **THEN** the run empties `/dst`, copies one more time, and goes on

#### Scenario: The source holds until the destination ended
- **WHEN** a move runs its copy
- **THEN** the source side runs `tar -C /src --numeric-owner --sparse -cpf - . && exec cat` with `kubectl exec -i`, and reads its stdin from the named pipe
- **AND** the destination side writes its stdout to the same named pipe
