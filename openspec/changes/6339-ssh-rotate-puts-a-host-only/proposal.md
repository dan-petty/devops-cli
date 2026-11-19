# Proposal

## Why

`devops ssh rotate` gives each rotated key GitHub access and makes it the git signing key. The `ansible` prefix is only for the nodes: `devops infra` hands that key to Ansible, and the homelab role puts it on each host. After a rotation the key that every node holds is a GitHub credential with the access of the account, and a commit in a repository with no local signing key is signed with the node key. Each rotation also adds one authentication key and one signing key to the account. #6339 stops that: only the project prefix registers and signs, and every other prefix reaches hosts only.

## What Changes

- `src/devops_cli/github/ssh.py:def register_key_on_github` gets a sibling `registers_on_github(prefix, project_prefix)`: it folds each `_` of both prefixes to `-`, as the key selection of `src/devops_cli/crypto/ssh_keys.py:def list_managed_keys` does, and returns true only when the two folded prefixes are equal.
- `src/devops_cli/github/ssh_plans.py:def plan_rotate` gets the keyword `github_enabled: bool = True` and returns an empty list when it is false, so a host-only dry run lists no GitHub key request and no `git config` command.
- `src/devops_cli/commands/ssh.py:def rotate` compares the prefix it already resolves with the project prefix through `registers_on_github`, and makes no registration call, no signing call and no grace notice for a prefix that is not the project prefix.
- A host-only rotation prints the new public key and one line that tells the person to put it on the hosts, so the node key stops being a GitHub credential.
- `src/devops_cli/lang/en/messages.py:class SSHMessages` gets `host_only_public_key` and `host_only_key_instruction`.
- The docstring of `src/devops_cli/commands/ssh.py:def rotate` says that only the prefix in `ssh.key_prefix` registers on GitHub and that every other prefix is for hosts only.
- New cases in `tests/crypto/test_ssh.py` and `tests/github/test_github_ssh.py` cover the host-only rotation, the project rotation, the host-only dry run and the help.
- `docs/commands/ssh.md` and `docs/CLI_REFERENCE.md` are regenerated with `uv run devops docs generate`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ssh-key-rotation`: A host-only prefix registers on no GitHub account, The project prefix registers and signs, A host-only rotation prints the host instruction, The rotate help names the prefix that registers

### Modified Capabilities

- `command-dry-run-class`: ssh-request-plans

## Impact

- Code: `src/devops_cli/github/ssh.py`, `src/devops_cli/commands/ssh.py`, `src/devops_cli/github/ssh_plans.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/commands/ssh.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/github/test_github_ssh.py`, `tests/crypto/test_ssh.py`

## Feasibility

- This reply fixes the three findings of the review: `criteria` now holds one entry for each item of the list in the alternatives block of the body, copied word for word, with the group that delivers it.
- `read_spec` of `command-dry-run-class` returned the base requirement `ssh-request-plans` with its three scenarios `Dry run on ssh register`, `Dry run on ssh rotate` and `The plan matches the real run`; the modified entry below keeps all three and adds `Dry run of a host-only prefix`.
- `probes` answered, word for word, "The path `src/devops_cli/commands/ssh.py` is a file of the staging commit.", and `read_file` of that module, lines 233 to 334, showed `src/devops_cli/commands/ssh.py:235:` `def rotate(`, the command that the issue cites.
- `probes` answered, word for word, "The path `src/devops_cli/github/ssh.py` is a file of the staging commit.", and `read_file` of that module showed `src/devops_cli/github/ssh.py:25:` `def register_key_on_github(pub_key: str, title: str) -> None:`, the registration call that `rotate` makes today.
- `probes` answered, word for word, "The path `src/devops_cli/crypto/ssh_keys.py` is a file of the staging commit.", and `read_file` of that module showed `src/devops_cli/crypto/ssh_keys.py:327:` `def configure_git_signing(key_path: Path, repo_dir: Path | None = None) -> None:`.
- `probes` answered, word for word, "The path `ssh.rotation_days` is no file of the staging commit. No commit in the history deleted or renamed it.", so the rotation age is a setting and no path; `read_file` of the settings showed `src/devops_cli/config/settings.py:353:` `rotation_days: Annotated[int, Variable()] = Field(` and `search_code` showed `src/devops_cli/config/defaults.py:53:DEFAULT_SSH_ROTATION_DAYS = 90`, so the 90 days of the issue are the default and no stale path.
- `read_file` of the ssh command module, lines 233 to 334, showed the prefix resolution at `src/devops_cli/commands/ssh.py:266:` `active_prefix = (`, the two calls with no test of the prefix at `src/devops_cli/commands/ssh.py:317:` `register_key_on_github(pub_key, _rotated_title(active_prefix))` and `src/devops_cli/commands/ssh.py:318:` `_configure_git_signing(new_key_path)`, and the removal notice at `src/devops_cli/commands/ssh.py:332:` `MESSAGES.ssh.grace_period_notice.format(name=newest.name, grace_days=CONST_SSH_GRACE_DAYS),` — the defect that the issue cites.
- `read_file` of the same module, lines 40 to 50 and 151, showed `src/devops_cli/commands/ssh.py:43:` `def _configure_git_signing(key_path: Path) -> None:` and `src/devops_cli/commands/ssh.py:151:` `def register(`, so the signing wrapper is one helper and `register` also takes `--prefix`; the host-only rule therefore names `rotate` alone.
- `read_file` of the key module, lines 260 to 334, showed `src/devops_cli/crypto/ssh_keys.py:307:` `def git_signing_commands(key_path: Path, repo_dir: Path | None = None) -> list[list[str]]:` and `src/devops_cli/crypto/ssh_keys.py:332:` `for command in git_signing_commands(key_path, repo_dir):`, so the signing commands come from one function and the local ones run only when the working directory is a repository.
- `read_file` of the key module also showed that the prefix `devops-cli` matches the key named `devops_cli-...`: the docstring of `src/devops_cli/crypto/ssh_keys.py:def list_managed_keys` says that a hyphen and an underscore are the same separator, so the new rule folds the same way and agrees with the key selection.
- `search_code` for `CONST_SSH_GRACE_DAYS` returned `src/devops_cli/config/constants.py:1498:` `CONST_SSH_GRACE_DAYS = 7`, the grace that the removal notice names; the plan keeps that notice for the project prefix only.
- `search_code` for `class SSHMessages` returned `src/devops_cli/lang/en/messages.py:2062:` `class SSHMessages:`, the class where the two new lines go, and `read_file` of lines 2062 to 2102 showed `src/devops_cli/lang/en/messages.py:2100:` `grace_period_notice: str = "\nOld key {name} remains active for {grace_days} grace days. Remove manually from GitHub when ready."`, the line that a host-only rotation must not print.
- `read_file` of the plan builder showed `src/devops_cli/github/ssh_plans.py:21:` `def plan_register(key_path: Path | str, title: str, condition: str = "") -> list[PlannedRequest]:` and `src/devops_cli/github/ssh_plans.py:50:` `def plan_rotate(key_path: Path, title: str) -> list[PlannedRequest]:`, and its import at `src/devops_cli/github/ssh_plans.py:16:` `from devops_cli.github.ssh import key_requests`, so the plan builder already imports the registration module and the new rule adds no import cycle.
- `search_code` for `registers_on_github` and for `host_only_public_key` returned no match, so the rule function and the two message lines are new and group 1 and group 2 add them.
- `read_file` of `tests/github/test_github_ssh.py`, lines 1 to 40, showed `tests/github/test_github_ssh.py:19:` `from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github`, so the cases of the rule go in the module that already tests the registration module.
- `read_file` of `tests/crypto/test_ssh.py`, lines 722 to 758, showed `tests/crypto/test_ssh.py:722:` `_PROJECT_PREFIX = "devops-cli"`, `tests/crypto/test_ssh.py:724:` `_OTHER_PROJECT_KEYS = ["alpha-id_ed25519-20260901", "beta_svc-id_ed25519-20260915"]`, `tests/crypto/test_ssh.py:738:` `def global_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:` and `tests/crypto/test_ssh.py:748:` `def key_dir_of_three_projects(`, so the fixture of three projects already holds an `alpha` key and a host-only rotation of that prefix is a case of the existing module.
- `read_file` of the same module, lines 860 to 955, showed `tests/crypto/test_ssh.py:867:` `def _accept_keys(github_api: GitHubApiFake) -> None:`, `tests/crypto/test_ssh.py:873:` `def test_register_adds_the_key_of_the_project_to_github(` and `tests/crypto/test_ssh.py:937:` `def test_rotate_replaces_the_key_of_the_project_and_leaves_the_keys_of_other_projects(`, so the new cases follow a shape that already reads the signing key from the temporary global config.
- `read_file` of `tests/support/fakes/github.py`, lines 485 to 500, showed `tests/support/fakes/github.py:489:` `def github_api(`; `register_key_on_github` needs a client of GitHub as a precondition of the call, and the `github_api` fake is that client, so the cases need no token and no network.
- `configure_git_signing` needs the `git` binary and a checkout of the working directory when it writes the local config, as preconditions of the call; the cases set `GIT_CONFIG_GLOBAL` to a temporary file through the `global_git_config` fixture and run in a directory with no `.git`, so no user config and no network is touched.
- `load_settings` reads the config file of the temporary home that the `config` fixture writes, and the key directory is read only: no checkout, no client and no network.
- The first checks against the real system are `uv run devops ssh rotate --prefix ansible --dry-run`, which must list no GitHub request and no `git config` command, then `uv run devops ssh rotate --prefix ansible --force --key-dir <temporary dir>` on a scratch key directory, which must print the public key and the host instruction and make no GitHub request, then `uv run devops ci test tests/crypto/test_ssh.py tests/github/test_github_ssh.py`.
- No command and no verify program is new: each verify is the existing `uv run devops ci test` or `uv run devops ci docs` row, the image holds `uv`, `python`, `pytest`, `devops` and `git`, and the pod keeps `runAsNonRoot: true`, `readOnlyRootFilesystem: true` and the drop of all capabilities, so no failure class and no runner capability is new.
- The rule compares the active prefix with the project prefix and names no list of prefixes, so no member is removed, restricted or allowlisted. No tool of this run counts the prefixes in use, so the count is unverified; group 2 writes the case that decides the project prefix and a host-only prefix, and the step stops when a prefix other than the configured one registers.
- `find_issues` for `ssh rotate` returned `#6339 open fix(security): ssh rotate puts a host-only key on GitHub` and `#5120 open feat(infra): manage infra repos with devops infra`; #5120 changes the infra repo management and no path of this change, so it is no dependency and no overlap, and the context lists no overlap and no metric sender.
- The homelab role that puts the key on the hosts and the `devops infra` path that hands the key to Ansible are outside this repository, and this run checked neither: not checked.

## Existing Tool Considered

No open, maintained tool covers the need: the alternatives check of 2026-11-19 in the issue body records the verdict `none` after four searches, and the need is a conditional inside the project's own rotate command and plan builder. The change builds its own code: about 30k tokens to build and test, about 5k tokens for each later change to keep, and less than one day of elapsed time. It deletes no internal code.

## Dependencies

None.
