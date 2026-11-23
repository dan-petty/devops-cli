## MODIFIED Requirements

### Requirement: The plan runs the playbook in check mode
The command SHALL run `ansible-runner run` with `--check --diff -v`, the inventory of the profile, `--tags` when given, the key of `devops ssh` as `ansible_ssh_private_key_file`, the repo's `ansible.cfg` and host key checks on. Before the run it SHALL install the pinned collections of the discovered requirements file (`collections/requirements.yml` or `collections/requirements.yaml`) once for each version of that file.

#### Scenario: The run options
- **WHEN** a person plans `ansible/playbooks/03_k3s.yaml` with `--limit node-5.example.com --tags k3s`
- **THEN** `ansible-galaxy collection install` runs before `ansible-runner`, and `ansible-runner` gets `--playbook ansible/playbooks/03_k3s.yaml`, `--limit node-5.example.com:!offline`, the command line `--check --diff -v -i ansible/inventory/hosts.yaml --tags k3s -e ansible_ssh_private_key_file=<key>` and `ANSIBLE_HOST_KEY_CHECKING=True`

#### Scenario: The collections install once
- **WHEN** a person plans twice at the same commit
- **THEN** `ansible-galaxy` runs once and `ansible-runner` runs twice

#### Scenario: A playbook outside the repo
- **WHEN** a person plans `../outside.yaml`
- **THEN** the command exits 1, says that it is not a playbook file of the infra repo, and starts no `ansible-runner`

#### Scenario: Plan on a YAML-only repository
- **WHEN** the project has only `collections/requirements.yaml` and no `collections/requirements.yml`
- **THEN** the install step installs the pinned collections from `collections/requirements.yaml`
