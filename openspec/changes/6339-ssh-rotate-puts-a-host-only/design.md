# Design

## Decisions

- **Compare the active prefix with `ssh.key_prefix` and treat every other prefix as host-only.**: The command already resolves that prefix at `src/devops_cli/commands/ssh.py:266:` `active_prefix = (`, so no second list can disagree with it, the default prefix that both sides resolve to still registers, and a typo in `--prefix` makes a host-only key and never a GitHub credential.
- **Keep the rule in one function, `registers_on_github`, beside the registration call `src/devops_cli/github/ssh.py:25:` `def register_key_on_github(pub_key: str, title: str) -> None:`.**: One rule serves the live run and the dry run, and the plan builder already imports that module for `key_requests` at `src/devops_cli/github/ssh_plans.py:16:` `from devops_cli.github.ssh import key_requests`, so the new function adds no import cycle.
- **Pass `github_enabled=False` from the command to `src/devops_cli/github/ssh_plans.py:50:` `def plan_rotate(key_path: Path, title: str) -> list[PlannedRequest]:`, which then returns an empty list.**: The plan builder stays a pure request builder, and the live run and the dry run use one decision.
- **Apply the host-only rule to `ssh rotate` alone and leave `ssh register` unchanged.**: The issue names `rotate`, and `src/devops_cli/commands/ssh.py:151:` `def register(` exists to put a key on GitHub, so the rule would leave it with nothing to do; the spec sentence names `rotate` so the dry run of `register` keeps listing its two key requests and its `git config` commands.
- **Print the new public key and one host instruction for a host-only prefix, and no GitHub removal line.**: The expected behavior of the issue asks for the instruction, and the old host key was never on GitHub, so a removal line for it would be false.
- **Run no `devops infra apply` from `rotate` to push the key to the hosts.**: That path needs a saved infra plan and an agent access level above `none`, and only a person sets that level.
- **Patch the GitHub edge with the `github_api` fake and read the signing result from the file of `tests/crypto/test_ssh.py:738:` `def global_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:`.**: The cases need no network, no GitHub account and no real user config, and they assert that a host-only rotation sends no request and writes no signing key.

## Rejected alternatives

- **Add a list of host-only prefixes to the config.**: A prefix that nobody adds to the list stays a GitHub key, so the defect remains for each new prefix, and the list adds a schema and a migration for a distinction that `ssh.key_prefix` already makes.
- **Add a `--github` or `--no-github` flag to `rotate`.**: A person must remember the flag on each run, and `make ssh-rotate` in the homelab repository keeps the defect on its default path.
- **Gate `plan_register` and `register` by the project prefix as well.**: `src/devops_cli/commands/ssh.py:151:` `def register(` exists to put a key on GitHub, so the gate would leave the command with nothing to do for a host-only prefix, and the issue asks for the `rotate` path only.
- **Let the plan builder read the prefix and the settings itself.**: It adds config and command concerns to `src/devops_cli/github/ssh_plans.py:50:` `def plan_rotate(key_path: Path, title: str) -> list[PlannedRequest]:`, which reads no settings, and it can disagree with the live run.
- **Build the dry-run plan in the command and stop calling the plan builder.**: The dry run and the live run would then have two request lists, which the docstring of `src/devops_cli/github/ssh_plans.py:3:` `A dry run makes zero external requests and returns ordered PlannedRequest items. The key` rules out.
- **Copy the prefix check at each call site.**: The copies drift, and one copy can skip the check.
- **Put the rule in the command module.**: The plan builder would import the command module, and the command module imports the plan builder at `src/devops_cli/commands/ssh.py:271:` `from devops_cli.github.ssh_plans import plan_rotate`, which is an import cycle.
- **Write the new key into the infra repository for Ansible.**: It couples the SSH command to one infra repository and needs a commit and a review for a key.
- **Show the GitHub removal message for every prefix.**: It tells the person to remove from GitHub a key that GitHub never held, and `src/devops_cli/commands/ssh.py:332:` `MESSAGES.ssh.grace_period_notice.format(name=newest.name, grace_days=CONST_SSH_GRACE_DAYS),` names GitHub only.
- **Use a real GitHub session in the cases.**: It needs a token and a live account and changes the account on each run.
- **Read only the source code and run no command in the cases.**: That does not show that the command leaves the git config unchanged; the cases read the temporary global config file after the run.

## Security

Before the change, a rotation of the `ansible` prefix put a key that every node holds on the GitHub account as an authentication key and as a signing key, so each node held the access of the account and commits were signed with the node key. After the change that key crosses no trust boundary: only the project prefix sends the key to GitHub and runs the git signing commands, and a host-only prefix prints the public key with one host instruction. A person must confirm that `ssh.key_prefix` names the key that belongs on the account, and must put the host key on the nodes with the infra role. `test_rotate_of_a_host_only_prefix_sends_no_request_and_runs_no_git_command` fails when a host-only rotation sends a request or runs a git config command.
