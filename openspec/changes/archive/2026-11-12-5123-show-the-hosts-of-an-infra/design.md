# Design

## Decisions

- **The Kubernetes API first, then the export.** The command reads the nodes before it fetches `origin`, so a cluster that does not answer stops the command before the fetch. Both reads are read-only.
- **One `stat` run for `--ping`.** `ansible.builtin.stat` on `/run/reboot-required` connects to the host, starts its Python and reads the file. A reachable host and a waiting reboot come from one event. An `ansible.builtin.ping` run first would add a second connection to each host for no new fact.
- **The export is the private data folder of ansible-runner.** ansible-runner starts `ansible` in its private data folder, and Ansible reads the `ansible.cfg` of its working folder. The export holds the repo's `ansible.cfg`, so the run reads the same config and inventory as a person who runs `ansible` in the repo. The artifacts go to a separate private folder (`--artifact-dir`), which the command removes after it reads the events. `--omit-env-files` writes no environment file.
- **Safe defaults for a read.** Host key checks on (`ANSIBLE_HOST_KEY_CHECKING=True`, because ansible-runner turns them off when the environment does not set them), `-e ansible_become=false` (a read needs no root), and `-T 10` (the connection bound ends before the run's bound of 300 s). The key of `devops ssh` goes in as `ansible_ssh_private_key_file` when it exists.
- **The level check is one function.** `require_agent_level(level, needed, action, repo)` in `infra/access.py` compares the levels in their order. A person passes at every level. `plan`, `apply` and `node` use the same function.
- **The rows are a model.** `StatusReport` holds the commit, the kube context and one `HostStatus` for each row, so `--format json` and `yaml` give the same facts as the table.

## Rejected alternatives

- **`kubectl get nodes -o json`.** The `KubernetesService` client already reads the nodes in the process, with its cache and its fake for tests.
- **Read the hosts from the working tree.** The working tree can be on another branch (#5162).
- **`ansible-runner -j` and its standard output.** The job events in the artifact folder are the same events, written one file for each event, with no other output between them.
