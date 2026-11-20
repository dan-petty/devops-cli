# Proposal: #4362

## Why

Some product code finds a tool in the installer folder of `devops install-tools` and not on PATH. The review lookups of `ruff` (`_default_ruff_block_checker` in `review/analysis.py`) and `semgrep` (`_resolve_semgrep_binary` in `review/rules_pack.py`) put `~/.local/bin` (`DEFAULT_LOCAL_BIN_DIR`) before PATH. `ansible_tool` in `infra/ansible_facts.py` looks first in the pinned install of `devops install-tools` under the user data root. When an image or a package manager installs a tool in another folder, the lookup misses it or finds a different copy. The owner decided on 2026-11-19 that every tool comes from the devtools image on PATH, and #4363 removes the installer. Closes #4362.

## What Changes

- The `ruff` of the Python block check and the `semgrep` of the rule pack test come from `require_binary` (`devops_cli.core.binaries`). With no tool on PATH, the call raises `DependencyError` with an install hint that names the upstream install page and the devtools image. Before, a missing `ruff` failed each Python block in silence, and a `semgrep` in `~/.local/bin` came before the one on PATH.
- `ansible_tool` takes the folder of the `ansible-runner` on PATH and no other folder. With no `ansible-runner` on PATH, the environment has no folder, and a dry run shows each Ansible command with no folder.
- The pinned version of the Ansible environment goes: `AnsibleTool.version`, the `ansible-core <version>` text of the onboard tool row and the `ansible_core` field of the plan record. Only the pinned install gave a value, so the field was empty for each `ansible-runner` on PATH.
- The infra messages name the upstream install page of ansible-runner, not `devops install-tools`.
- The infra test fixture `ansible_installed` puts a stand-in `ansible-runner` on PATH. The dry-run snapshots name the folder of the stand-in, not the pinned install folder with its version.
- `devops install-tools` keeps its behavior until #4363 removes it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-onboard`: the tool row and the Ansible environment come from the `ansible-runner` on PATH.
- `infra-plan`: the plan record holds no ansible-core version.
- `review-tool-runs`: the review finds `ruff` and `semgrep` on PATH only.

## Impact

- Code: `src/devops_cli/review/analysis.py`, `src/devops_cli/review/rules_pack.py`, `src/devops_cli/infra/ansible_facts.py`, `infra/onboard.py`, `infra/plan.py`, `infra/status.py`, `models/infra.py`, and the messages in `lang/en/`.
- Tests: `tests/support/infra.py`, the infra tests and snapshots, `tests/commands/test_review_rules_pack.py`, `tests/review/test_review_group_analysis.py` and the new `tests/infra/test_ansible_facts.py`.
- Users: a host that has a tool only in `~/.local/bin` or in the installer folder, and not on PATH, now gets the install hint. A plan record has no `ansible_core` field. An old record with the field still loads, because the model ignores an unknown field.

## Feasibility

- `git grep -nE 'tool_install_dir|installed_commands|DEFAULT_LOCAL_BIN_DIR' origin/main -- src` named `review/analysis.py:821`, `review/rules_pack.py:208`, `infra/ansible_facts.py:74-75`, `commands/install_tools.py` and the tools_lock package on 2026-11-20.
- `require_binary` and `check_binary` wrap `shutil.which`, and `docs/SDLC.md` requires them.
- In the devcontainer, `/usr/local/bin/semgrep` is a link into `/usr/local/lib/devtools/semgrep/bin`, and `ruff` is in the project venv on PATH.

## Existing Tool Considered

The Python standard library `shutil.which` covers the need, through `check_binary` and `require_binary` of `devops_cli.core.binaries`. The change writes no new lookup.
