# Design

## Decisions

- **One lookup.** Each tool comes from `require_binary`, which raises `DependencyError` with an install hint. `ansible_tool` first asks `check_binary`, because a missing `ansible-runner` is a row of the onboard report and not an error.
- **The resolved folder of `ansible-runner`.** `require_binary` resolves the link on PATH. The devtools image links only `ansible-runner` into `/usr/local/bin`, and the other Ansible commands are beside the resolved file.
- **No folder for a missing environment.** `AnsibleTool.bin_dir` is `None` when no `ansible-runner` is on PATH. `installed` is a property of the folder. `argv` gives the bare command name, so a dry run shows a command that a person can read.
- **No version of the Ansible environment.** The version came from the pin of `tools.lock` and only for the install of `devops install-tools`. The record and the row drop it, and no code reads the version of the installed tool, because no reader needs it.
- **The hint names the upstream install page.** It does not name `devops install-tools`, which #4363 removes.
- **The test fixture.** `ansible_installed` writes a stand-in `ansible-runner` and answers the PATH lookup of `process_fake` for that name. The stand-in folder holds no version.

## Rejected alternatives

- Keep `~/.local/bin` as a second search folder: the owner decision of 2026-11-19 makes PATH the one source.
- Read the ansible-core version of the installed tool for the plan record: no reader uses the field, and the item prefers to delete code.
- Fall back to the bare command name when the tool is missing: the subprocess then fails with no install hint, and a missing `ruff` dropped each analysis in silence.
