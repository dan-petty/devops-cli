## ADDED Requirements

### Requirement: A volume move measure plans the copy command of the move
The measure SHALL plan each copy with `copy_argv` and SHALL compare the two sides with `digest_args` and the digest script `CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT`.

#### Scenario: The measure plans the copy command of the move
- **WHEN** The measure plans one copy in its temporary namespace
- **THEN** The planned command holds the named pipe and the two exec streams, and each side is read with the digest script

### Requirement: A volume move measure runs twenty copies of 100 MiB
The measure SHALL make 20 copies of 104,857,600 bytes of random source data, one after another, and SHALL write fresh random data to the source claim before each copy.

#### Scenario: Twenty copies of 100 MiB
- **WHEN** The measure plans its copies with no option
- **THEN** The plan holds 20 copies of 104857600 bytes

### Requirement: A volume move measure places its two copy pods on two nodes
The measure SHALL run its source pod on the node that `--source-node` names and its destination pod on the node that `--target-node` names, each through a nodeSelector on the hostname label, and SHALL refuse two equal node names.

#### Scenario: Each copy pod selects its node
- **WHEN** The measure renders its two pods for the source node node-a and the target node node-b
- **THEN** The source pod selects node-a, the destination pod selects node-b, and the plan refuses node-a as both nodes

### Requirement: A volume move measure fails a copy whose digest differs
The measure SHALL compare the content digest of each copy's source with the content digest of its destination, and the report SHALL fail when the two differ.

#### Scenario: A mismatch fails the report
- **WHEN** The report reads 20 complete copies and one destination digest differs from its source
- **THEN** The report exits non-zero and names the mismatched copy

### Requirement: A volume move measure reports its complete copies and digest matches
The report of the measure SHALL print a Markdown table with the number of complete copies and the number of digest matches, and the run SHALL exit non-zero when fewer than 20 copies complete with a matching digest.

#### Scenario: All copies match
- **WHEN** The report reads 20 complete copies whose digests match
- **THEN** The report prints 20/20 complete copies and 20/20 digest matches, and the run exits 0

#### Scenario: One copy is short
- **WHEN** The report reads 19 complete copies and one short copy
- **THEN** The run exits non-zero and names the short copy

### Requirement: A volume move measure removes its temporary namespace
The measure SHALL create one temporary namespace and SHALL delete it when the run ends, whether the copies passed or failed.

#### Scenario: A failed copy still cleans up
- **WHEN** A copy fails during a run against the fake cluster
- **THEN** The run sends the delete of the temporary namespace and exits non-zero

### Requirement: The dry run of a volume move measure makes no request
The dry run of the measure SHALL start no process and SHALL print the requests of a run in order.

#### Scenario: The dry run lists the requests
- **WHEN** The dry run runs for two named nodes
- **THEN** It prints the create of the namespace, the two claims, the two pods and the 20 copies, and it starts no process
