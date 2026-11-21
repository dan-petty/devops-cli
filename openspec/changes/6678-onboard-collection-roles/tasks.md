# Tasks

## 1. The roles row lists the roles of the pinned collections

Kind: behavior. Reads: `src/devops_cli/infra/onboard.py`, `src/devops_cli/infra/plan.py`, `src/devops_cli/infra/ansible_facts.py`, `src/devops_cli/infra/repo_content.py`, `src/devops_cli/infra/infra_plans.py`, `tests/support/infra.py`. Changes: `src/devops_cli/infra/onboard.py`, `src/devops_cli/infra/ansible_facts.py`, `src/devops_cli/infra/plan.py`, `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/lang/en/messages.py`, `tests/infra/test_onboard.py`, `tests/support/infra.py`, `tests/commands/__snapshots__/test_infra_onboard.ambr`, `tests/fixtures/infra/collections/example/infra/`, `tests/fixtures/infra/ansible_roles.json`.
Adds: `install_requirements`, `read_collection_roles`, `role_list_argv`, `ROLE_LIST_ARGS`, `DOC_COMMAND`, `config_env`

- [ ] 1.1 Add the fixture collection `tests/fixtures/infra/collections/example/infra/` (role `nvidia` with an argument spec) and its recorded listing `tests/fixtures/infra/ansible_roles.json`. In `answer_infra_reads` of `tests/support/infra.py`, answer `ansible-galaxy collection install` with a copy of each fixture collection that the requirements file names into the `-p` folder, and `ansible-doc -t role -l -j` with the recorded listing when `ANSIBLE_COLLECTIONS_PATH` holds `example.infra`, else `{}`. Write the failing tests `test_the_roles_row_lists_the_roles_of_the_pinned_collections`, `test_without_ansible_doc_the_roles_row_keeps_the_role_folders` and `test_a_failed_install_keeps_the_roles_of_the_role_folders` in `tests/infra/test_onboard.py`, and change `test_the_report_fetches_origin_and_reads_only_local_tools` to `test_the_report_fetches_origin_and_installs_the_pinned_collections` with the install and the listing in its list of calls. Add the install and the listing to the snapshot of `test_dry_run_starts_no_process_and_writes_nothing`
  - Verification: `$ uv run devops ci test tests/infra/test_onboard.py tests/commands/test_infra_onboard.py` fails on the base
- [ ] 1.2 Move `REQUIREMENTS_FILE`, `galaxy_argv` and `_config_env` (as `config_env`) from `src/devops_cli/infra/plan.py` to `src/devops_cli/infra/ansible_facts.py`, and add `install_requirements`, which runs the install of `install_collections` into a folder that the caller gives. `install_collections` keeps its kept install and calls it. Add `read_collection_roles`, which runs `ansible-doc -t role -l -j` with `ANSIBLE_COLLECTIONS_PATH` and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False` and returns each role that names a collection. In `src/devops_cli/infra/onboard.py`, install into a temporary folder and add the roles to the roles row after the roles of the role folders, or say in the reason why the row does not list them. Add the install and the listing to `plan_onboard` of `src/devops_cli/infra/infra_plans.py`. Change the module docstrings that say the fetch is the only request
  - Verification: `$ uv run devops ci test tests/infra/test_onboard.py tests/commands/test_infra_onboard.py tests/commands/test_infra_plan.py tests/commands/test_infra_apply.py` passes

## 2. Documents

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `docs/commands/infra.md`. Changes: `src/devops_cli/lang/en/help.py`, `docs/commands/infra.md`, `docs/CLI_REFERENCE.md`.

- [ ] 2.1 In the help text of `devops infra onboard` in `src/devops_cli/lang/en/help.py`, say that the check installs the pinned collections of the repo into a temporary folder to list their roles, then run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- After dan-petty/homelab#76 merges, `uv run devops infra onboard dan-petty/homelab` in a devops-cli checkout lists `dan_petty.infra.nvidia` (dan-petty/homelab#76).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
