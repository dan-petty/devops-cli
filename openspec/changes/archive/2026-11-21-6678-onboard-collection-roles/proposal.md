# Proposal: #6678

## Why
Closes #6678. `devops infra onboard` lists the roles of an infra repo with `find_roles` over the folders of `roles_path` (`src/devops_cli/infra/onboard.py:383`). After dan-petty/homelab#76, homelab runs its node roles from the pinned collection `dan_petty.infra`. Its `ansible/roles` folder then holds fewer roles, and the roles row does not show the roles that moved to the collection.

## What Changes
- The roles row of `devops infra onboard` also lists the roles of the pinned collections. When the export of the default branch holds `collections/requirements.yml`, onboarding installs its collections with `ansible-galaxy collection install -r <file> -p <folder>` into a new temporary folder. It then reads `ansible-doc -t role -l -j` in the export with `ANSIBLE_COLLECTIONS_PATH=<folder>` and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False`. The row adds each role of the listing that names a collection, by its full name, after the roles of the role folders. The folder is removed after the read. Project code reads no file of a collection.
- When the Ansible tool environment holds no `ansible-doc`, or no tool environment is installed, the row keeps the roles of the role folders and starts no install. Its reason says that the row does not list the roles of the pinned collections. When the install or the listing fails, the row keeps the roles of the role folders, and its reason names the command, its exit code and its last line.
- The install helper of `plan.py` moves to `ansible_facts.py` (`REQUIREMENTS_FILE`, `galaxy_argv`, `config_env` and the new `install_requirements`), because `plan.py` imports `onboard.py`. `install_collections` of `plan.py` keeps its kept install and calls `install_requirements`. Plan and apply do not change.
- The dry run of onboard lists the install and the role listing. The help text of onboard says that the check installs the pinned collections into a temporary folder. The step of the roles row also names a role of a pinned collection.
- The row, the requests of the command and its dry run change, and a consumer sees them, so the change carries spec deltas for `infra-onboard`.
- The change fits one pull request.

## Capabilities
- `infra-onboard`: ADDED requirements "The roles row lists the roles of the pinned collections" and "The roles row keeps the role folders when the collections do not read". MODIFIED requirements "One row for each check" (the reads and the requests) and "A dry run starts nothing" (the commands that the dry run lists).

## Impact
- An onboarding of a repo that holds `collections/requirements.yml` makes more requests: the install of its pinned collections from Galaxy or from their git sources. The install has the bound of the install of plan, `DEFAULT_INFRA_GALAXY_TIMEOUT_SECONDS` (600 s).
- A role of a collection shows in the row only when it has an argument spec (`meta/argument_specs.yml`), because `ansible-doc` lists only those roles. dan-petty/infra#7 and dan-petty/infra#8 add the argument specs of `dan_petty.infra`.
- No setting and no stored data changes.

## Feasibility
- Code at origin/main `52126dbd4`: `_roles_row` (`src/devops_cli/infra/onboard.py:380`) calls `find_roles` over the folders of `roles_path`. `install_collections` (`src/devops_cli/infra/plan.py:415`) runs `ansible-galaxy collection install -r <file> -p <folder>`. `plan.py:80` imports `OnboardTarget` from `onboard.py`, so `onboard.py` cannot import `plan.py`.
- ansible-core 2.22.0, the tool environment of the devcontainer (its `bin` folder holds `ansible-doc` and `ansible-galaxy` beside `ansible-runner`): `ansible-galaxy collection build` and `install` of the test collection `example.infra` put it in `<folder>/ansible_collections/example/infra`. Then `ansible-doc -t role -l -j`, with `ANSIBLE_COLLECTIONS_PATH=<folder>` and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False` in a copy of `tests/fixtures/infra/homelab_shape`, prints `{"example.infra.nvidia": {"collection": "example.infra", ...}}` and exits 0. A role of a collection has the key `collection`, and a role of `roles_path` has no such key. A role with no argument spec is not in the listing.
- With an empty collections folder, the listing in the homelab shape is `{}`, because its roles have no argument spec.
- The sys path setting is necessary: with the `ansible` 2.21.4 community package, a probe listing holds 108 roles with `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=True`, most of them from the collections of that package, and 2 roles with `False` (1 of the probe's `roles_path` and 1 of its test collection).
- PATH: in the devcontainer, `ansible-runner` is on PATH, and its tool environment holds `ansible-doc`. The CI runner image (`ubuntu-26.04`, image version 20261116.202.1) lists Ansible 2.21.6. The tests double the process edge and the lookup of each program (ADR 0007), so they start no `ansible-doc` or `ansible-galaxy` and run the same on both hosts.

## Existing Tool Considered
- `ansible-doc -t role -l -j` of ansible-core (GPL-3.0, maintained, the tool environment of `devops infra`) lists the roles of the installed collections from their argument specs, and `ansible-galaxy collection install` installs the collections. The change uses both tools and walks no collection folder in project code.
- Build cost: about 80 lines of code and 4 tests; about 80k tokens and 1.5 hours to build. The cost to keep is low, because the listing and its JSON form come from ansible-core.
- The change deletes no internal code. It moves the install helper of `plan.py` to `ansible_facts.py`, and one copy stays.
