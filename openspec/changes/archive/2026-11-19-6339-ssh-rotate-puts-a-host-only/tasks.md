# Tasks

## 1. Add the rule that decides GitHub registration by prefix

Kind: behavior. Reads: `src/devops_cli/github/ssh.py`, `src/devops_cli/crypto/ssh_keys.py`, `tests/github/test_github_ssh.py`, `tests/crypto/test_ssh.py`. Changes: `src/devops_cli/github/ssh.py`, `tests/github/test_github_ssh.py`.
Adds: `registers_on_github`

- [x] 1.1 `test_only_the_project_prefix_registers_on_github` in `tests/github/test_github_ssh.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_ssh.py` fails on the base
- [x] 1.2 Add `registers_on_github(prefix, project_prefix)` to `src/devops_cli/github/ssh.py` beside `def register_key_on_github(pub_key: str, title: str) -> None:`. It folds each `_` of both prefixes to `-`, as the key selection of `src/devops_cli/crypto/ssh_keys.py:def list_managed_keys` does, and returns true only when the two folded prefixes are equal. Write the case first in `tests/github/test_github_ssh.py`: `devops-cli` matches `devops_cli`, `ansible` matches neither, and two empty prefixes match, so the default key still registers
  - Verification: `$ uv run devops ci test tests/github/test_github_ssh.py` passes

## 2. Gate the rotation and the dry run by the project prefix

Kind: behavior. Reads: `src/devops_cli/commands/ssh.py`, `src/devops_cli/github/ssh.py`, `src/devops_cli/github/ssh_plans.py`, `src/devops_cli/lang/en/messages.py`, `tests/crypto/test_ssh.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/commands/ssh.py`, `src/devops_cli/github/ssh_plans.py`, `src/devops_cli/lang/en/messages.py`, `tests/crypto/test_ssh.py`.
Adds: `host_only_public_key`, `host_only_key_instruction`

- [x] 2.1 `test_rotate_of_a_host_only_prefix_sends_no_request_and_runs_no_git_command`, `test_rotate_of_the_project_prefix_registers_and_signs`, `test_ssh_rotate_dry_run_of_a_host_only_prefix_lists_no_github_request` and `test_ssh_rotate_help_names_the_github_prefix` in `tests/crypto/test_ssh.py`
  - Verification: `$ uv run devops ci test tests/crypto/test_ssh.py` fails on the base
- [x] 2.2 In `src/devops_cli/commands/ssh.py`, compute the project prefix as `settings.ssh.key_prefix or get_ssh_key_prefix()`, the fallback of `active_prefix = (`, and set `github_enabled = registers_on_github(active_prefix, project_prefix)`. Pass `github_enabled=` to `plan_rotate`. When it is false in the live run, make no registration call, no signing call and no grace notice: print the new public key and one line that tells the person to put it on the hosts, and add the host-only line to the dry-run notes. Add `host_only_public_key` and `host_only_key_instruction` to `class SSHMessages:` in `src/devops_cli/lang/en/messages.py`. Give `def plan_rotate(key_path: Path, title: str) -> list[PlannedRequest]:` in `src/devops_cli/github/ssh_plans.py` the keyword `github_enabled: bool = True` and return an empty list when it is false. Say in the docstring of `rotate` that only the prefix in `ssh.key_prefix` registers on GitHub. Leave `register` and `plan_register` unchanged. Write the four cases first in `tests/crypto/test_ssh.py`, with the `github_api` fake, the `key_dir_of_three_projects` fixture and the `global_git_config` file: the host-only rotation sends no request and writes no signing key; the project rotation sends both keys and writes the new signing key into the global config; the host-only dry run lists no plan line; the help names `ssh.key_prefix`
  - Verification: `$ uv run devops ci test tests/crypto/test_ssh.py` passes

## 3. Regenerate the ssh command page and the CLI reference

Kind: other. Reads: `docs/commands/ssh.md`, `docs/CLI_REFERENCE.md`. Changes: `docs/commands/ssh.md`, `docs/CLI_REFERENCE.md`.

- [x] 3.1 Run `uv run devops docs generate`, the command of `src/devops_cli/commands/docs.py:def generate`, after the docstring of `rotate` changes. It writes the new help into `docs/commands/ssh.md` and the command summary of `docs/CLI_REFERENCE.md`. Change no line of them by hand
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Regenerate `docs/commands/ssh.md` and `docs/CLI_REFERENCE.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test: `rotate` of a prefix that is only for hosts makes no GitHub request and does not change the git config. It fails on `main` (`devops ci fail-to-pass`).
- Group 2: A test: `rotate` of the project prefix still registers the key and sets the signing.
- Group 2: The dry run of a prefix that is only for hosts lists no GitHub request.
- Group 3: The help and the reference of `devops ssh rotate` tell which prefixes go to GitHub.
- Group 1: No tool tells a host-only prefix from the project prefix
- Group 2: No tool gates GitHub key registration and signing by prefix
- Group 2: No tool edits the dry-run plan to drop GitHub requests

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
