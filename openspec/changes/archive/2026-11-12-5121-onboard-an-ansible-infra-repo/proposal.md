# Proposal: #5121 onboard an Ansible infra repo

## Why

Closes #5121. The owner asked on 2026-11-12 for native `devops` commands that manage an infrastructure environment kept in a git repository, first dan-petty/homelab, which holds an Ansible inventory, playbooks and roles. Every later `devops infra` command (status, plan, apply, drift, node; tracker #5120) needs to know which repositories are infra repos, where their checkouts are, how their Ansible content is laid out and what an agent may do on their hosts. Nothing records this now. The owner also asked to validate the onboarding live on the homelab repository.

## What Changes

- A new settings section `infra`: `plan_max_age_hours`, `drain_timeout_seconds`, `node_ready_timeout_seconds` and `repos`. Each entry of `repos` holds operational keys only: `repo` (owner/name), `path`, `kube_context`, `ssh_key_prefix` (default `ansible`) and `agent_access` (`none`, `plan`, `safe` or `full`; default `none`).
- The first project profile loader (#4627): `src/devops_cli/project/profile.py` resolves the `ProjectProfile` of a checkout from the field defaults, the type template `src/devops_cli/templates/profiles/<type>.toml`, detection in its files and its `.devops/project.toml`, in that order, and records the source of each value. It knows one type, `ansible-k8s`, detected by `ansible.cfg`, with the tables `[ansible]` (`inventory`, `playbook_dir`, `roles_path`, `offline_group`) and `[kubernetes]` (`dir`). The facts of an infra repo live there, not in the config of devops-cli. The later items of #4627 extend this loader: #4635 (toolchain presets), #4643 (stage plan rules) and #4664 with #3775 (onboarding detection).
- A Python tool `[python.ansible-core]` in `src/devops_cli/tools_lock/tools.lock`: one environment with ansible-core 2.22.0 and ansible-runner 2.4.3 from hashed requirements, which `devops install-tools` installs, and which the devcontainer image installs under `/usr/local/share/devops-tools/ansible-core`. Only `ansible-runner` goes on PATH. It is not a dependency in `pyproject.toml`.
- A new command group `devops infra` with one command, `devops infra onboard <repo>`. It reads the local checkout and local tool output only, and prints one row for each of 17 checks with a state (`present`, `missing`, `not readable` or `listed`), a reason and a step. With `--confirm`, it writes the entry of the repository into `infra.repos`. An agent caller cannot give an access level above `none`. `--dry-run` starts no process and writes nothing.
- `devops_cli/core/caller.py` holds the caller detection (agent tool, MCP call, cluster Job) that `telemetry/usage_errors.py` held, so the usage-error record and the access level read one source.
- The command, its options, its messages and its settings are observable, so the change has a spec delta: a new capability `infra-onboard`.

The change fits one pull request.

## Capabilities

- `infra-onboard` (new): the settings of an infra repo, its agent access level, the onboarding report and its write.
- `project-profile` (new): the project profile of a repository, its sources and their order.

## Impact

- New settings keys under `infra`, three new variables (`DEVOPS_CLI_INFRA_PLAN_MAX_AGE_HOURS`, `DEVOPS_CLI_INFRA_DRAIN_TIMEOUT_SECONDS`, `DEVOPS_CLI_INFRA_NODE_READY_TIMEOUT_SECONDS`) and four new error codes (`INFRA_ERROR`, `INFRA_ACCESS_REFUSED`, `INFRA_READ_FAILED`, `INFRA_REPO_NOT_FOUND`).
- `devops install-tools` and the devcontainer image install one more tool environment, 33 MB.
- `ansible-core` is GPL-3.0-or-later. It runs only as a child process from its own tool environment, so no GPL code loads into the devops process. ansible-runner is Apache-2.0.
- No command reaches a host or the Kubernetes API in this change.
- A repository can commit `.devops/project.toml`. Onboarding reads it from the checkout, and lists the values to declare when the file is absent. It writes nothing into the repository.

## Feasibility

- `uv pip compile --universal --python-version=3.14` of `ansible-core` and `ansible-runner` on 2026-11-12 resolved ansible-core 2.22.0 and ansible-runner 2.4.3, the versions of the design. `devops install-tools --tool ansible-core` installed them, and `ansible-runner --version` printed `2.4.3`.
- `ansible-config dump --format json --only-changed` of ansible-core 2.22.0 prints a list: one object (`name`, `origin`, `value`) for each changed base setting, such as `CONFIG_FILE`, `DEFAULT_HOST_LIST`, `DEFAULT_ROLES_PATH` and `HOST_KEY_CHECKING`, and one object for each plugin type, such as `{"CONNECTION_PLUGINS": [{"ssh": [...]}]}`, which holds `ssh_args` and `host_key_checking` of the `ssh` plugin. `ansible-inventory --list` prints the groups with `hosts` and `children`, and `_meta.hostvars` with the raw host variables. Neither command connects to a host.
- `ansible-doc -t callback -l` of ansible-core 2.22.0 lists `default`, `junit`, `minimal`, `oneline` and `tree`, and `oneline` and `tree` print a deprecation for removal in 2.23. No JSON stdout callback ships with ansible-core, so a machine-readable read of the `debug` action needs the event stream of ansible-runner. Onboarding needs only which `devops_infra_` variables a host sets, and `ansible-inventory --list` gives that. The rendered read comes with the event reader of `devops infra plan` (#5124).
- The live run on dan-petty/homelab `origin/main` (f5961bd) from an empty `DEVOPS_CLI_CONFIG` found 6 hosts in 6 groups, the group `offline` with 2 hosts, 17 playbooks, 5 roles, 14 tasks with `check_mode: false` and 16 Makefile targets that drain, uncordon or restart a node, as the design counted. It reported no `collections/requirements.yml` (the plays use `ansible.posix`, `community.general` and `kubernetes.core`), no CI workflow and no kube context. The same run on e022912, the commit before homelab#24, reported the four settings that turned host key checks off, one of them the inventory variable `ansible_ssh_common_args`.
- `get_repo_origin_name` (`core/repo.py`) gives the owner/name of the remote `origin` of a checkout, and `RepoRef` (`github/repo_ref.py`) parses it.
- No module on `main` defines `ProjectProfile` or reads `.devops/project.toml` (`git grep -n "ProjectProfile\|project.toml" -- src` finds none), and #4635 and #4643 are open. The generalization model (`profile.json` of the planning session of #4627) names the file, the template folder, the merge order and the merge rule that this loader follows.
- `service.repos` is a `list[str]` that 14 modules of `src/` read as repository names, its entries turn on every Service row for a repository (owner decision 1 of #4627), and it lives in the cluster ConfigMap. An infra repo needs a local path and an access level, and managing its hosts is not the same decision as running the Service rows on it. So the operational keys of an infra repo get their own table, `infra.repos`.

## Existing Tool Considered

Ansible's own commands give the facts: `ansible-config dump` and `ansible-inventory --list`. `ssh-keygen -F` reads `known_hosts`, hashed entries included. `kubectl config get-contexts` reads the kubeconfig. PyYAML composes the YAML files with no construction, and `packaging` judges an exact collection version. ansible-runner is the engine of the later commands, chosen over ansible-navigator, AWX and Semaphore in the design of #5120. The onboarding rows are glue around these tools: about 2.5M tokens to build, 0.3M tokens a quarter to keep and fix, and 4 hours. The profile loader uses `tomllib` and `configparser` of the standard library and pydantic. The change deletes no internal code: the caller detection moves from `telemetry/usage_errors.py` to `core/caller.py`.
