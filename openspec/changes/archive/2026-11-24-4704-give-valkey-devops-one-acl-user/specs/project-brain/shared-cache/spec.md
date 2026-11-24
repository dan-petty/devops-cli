## MODIFIED Requirements

### Requirement: A private repository's snapshot is shared only under the sweep user
The visibility check SHALL give public, private or unknown, and a failed read SHALL give unknown. The snapshot store SHALL write, read and keep the shared copy of a private repository only when the process sends the ACL user `sweep`, and SHALL remove that copy under any other user or none. The store SHALL write no shared key and read no record of a repository whose visibility is unknown. The shared copy of a private repository SHALL keep the key and the TTL of a public repository.

#### Scenario: Private repository
- **WHEN** A listing round runs for a repository whose visibility read gives `isPrivate: true` and the process sends no ACL user
- **THEN** The `valkey_server` fake holds no key that names the repository, the round reads GitHub, GitHub gets one visibility read, and `devops_cli_brain_reads_total{store="snapshot",result="private"}` and `devops_cli_brain_writes_total{store="snapshot",result="private"}` each rise by one

#### Scenario: Private repository under the sweep user
- **WHEN** A listing round runs for a repository whose visibility read gives `isPrivate: true` and the process sends the `sweep` user
- **THEN** The `valkey_server` fake holds the snapshot key of the repository with its metadata, and `devops_cli_brain_writes_total{store="snapshot",result="shared"}` rises by one

#### Scenario: The sweep user reads the shared copy of a private repository
- **WHEN** A process that sends the `sweep` user loads the listing of a private repository that the shared tier holds
- **THEN** The load gives the shared records and `devops_cli_brain_reads_total{store="snapshot",result="shared"}` rises by one

#### Scenario: No visibility read without the shared tier
- **WHEN** The `valkey_server` fake has `connected = False` and a listing round runs
- **THEN** The round sends no visibility read to GitHub

#### Scenario: A repository that became private
- **WHEN** A round of a public repository writes its shared snapshot, and a round in a new process that sends no ACL user finds that the repository is private
- **THEN** The `valkey_server` fake holds no key, the round uses no shared copy, and `devops_cli_brain_writes_total{result="removed"}` rises by one

## RENAMED Requirements

- FROM: `### Requirement: No key of a private repository`
- TO: `### Requirement: A private repository's snapshot is shared only under the sweep user`
