## MODIFIED Requirements

### Requirement: The roles row lists the roles of the pinned collections
When the export holds a collection requirements file (`collections/requirements.yml` or `collections/requirements.yaml`), the command SHALL install collections into a temporary folder with `ansible-galaxy collection install`, read `ansible-doc -t role -l -j` with that folder as collections path, and remove the folder. The roles row SHALL list role folders and each collection role by full name. The command MUST NOT read collection files directly.

#### Scenario: A role of a pinned collection
- **WHEN** `collections/requirements.yml` pins the collection `example.infra`, whose role `nvidia` has an argument spec
- **THEN** the roles row is `present` and lists the 5 roles of `ansible/roles`, then `example.infra.nvidia`, `ansible-doc` ran with `ANSIBLE_COLLECTIONS_PATH` set to the `-p` folder of the install and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH` set to `False`, and the folder no longer exists

#### Scenario: Onboard on a YAML-only repository
- **WHEN** `collections/requirements.yaml` pins the collection `example.infra` and no `collections/requirements.yml` exists
- **THEN** the roles row installs from `collections/requirements.yaml` and lists the roles of the pinned collection
