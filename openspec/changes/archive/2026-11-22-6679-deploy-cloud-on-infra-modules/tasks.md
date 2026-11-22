# Tasks

## 1. Deploy-cloud reads the infra layout

Kind: behavior. Reads: `src/devops_cli/commands/tf.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/tf/tf_plans.py`, `src/devops_cli/exceptions/validation.py`. Changes: `tests/commands/test_tf.py`, `tests/commands/test_tf_dry_run.py`, `src/devops_cli/commands/tf.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `docs/commands/tf.md`, `docs/CLI_REFERENCE.md`.
Adds: `CONST_TF_EXAMPLES_DIR`, `MESSAGES.tf.deploy_cloud_dir_not_found`

- [x] 1.1 In `tests/commands/test_tf.py`, build each `tmp_path` tree in the infra layout: `test_get_cloud_dir` expects `tf/examples/<provider>`, `test_get_default_var_file` writes `tf/examples/aws/aws.tfvars.example`, and `test_deploy_cloud_command`, `test_deploy_cloud_dry_run` and `test_deploy_cloud_targets_the_nested_worktrees_configuration` create `tf/examples/aws`. Add `test_a_dry_run_in_an_infra_checkout_plans_init_and_apply_of_its_example` for the scenario "A dry run in an infra checkout", and `test_deploy_cloud_outside_an_infra_checkout_names_one`, parametrized with the ids `run` and `dry-run`, for the scenario "Deploy-cloud in a checkout with no examples". In `tests/commands/test_tf_dry_run.py`, `test_request_plan_commands_make_no_external_request` runs `deploy-cloud` in a temporary checkout that holds `tf/examples/aws`. The changed and new tests fail on the base
  - Verification: `$ uv run devops ci test tests/commands/test_tf.py` fails on the base
- [x] 1.2 In `src/devops_cli/config/constants.py`, add `CONST_TF_EXAMPLES_DIR` (`tf/examples`), put `CONST_TF_AWS_DIR`, `CONST_TF_AZURE_DIR` and `CONST_TF_GCP_DIR` below it, and delete `CONST_TF_ENVIRONMENTS_DIR`. In `src/devops_cli/commands/tf.py`, `_get_default_var_file` gives `<provider>.tfvars.example` in the folder of `_get_cloud_dir`, and `deploy_cloud` raises `ValidationError` with the new message `deploy_cloud_dir_not_found` of `src/devops_cli/lang/en/messages.py` when that folder is not a directory. The docstring of `deploy_cloud` names the infra checkout. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_tf.py` passes

## 2. Delete the copy of the infra examples

Kind: other. Reads: `src/devops_cli/roadmap/step_rules.py`, `tests/roadmap/test_roadmap_step_rules.py`, `AGENTS.md`, `tests/research/test_inventory_repository.py`. Changes: `tf/`, `src/devops_cli/roadmap/step_rules.py`, `tests/roadmap/test_roadmap_step_rules.py`, `AGENTS.md`, `tests/security/test_tf_azure_aks_security.py`, `tests/research/test_inventory_repository.py`, `tests/gate/tree_checks/config_reads.toml`, `tests/module_durations.json`.

- [x] 2.1 Delete `tf/aws`, `tf/azure`, `tf/gcp`, `tf/environments` and `tf/README.md`. Delete the `tf/**` route of `src/devops_cli/roadmap/step_rules.py`, rename the row of the two `k8s/**` routes and of AGENTS.md to "change a manifest or the cluster", and delete the `tf` link of that row. Change `test_a_route_without_sections_gives_the_start_of_its_document_cut_to_the_cap` to build its route and a document over the cap in a temporary checkout. Delete `tests/security/test_tf_azure_aks_security.py`, which reads `tf/azure`, and its lines in `tests/gate/tree_checks/config_reads.toml` and `tests/module_durations.json`: the module `azure-aks` of infra keeps the authorized ranges with no default and a validation. `test_the_repository_has_at_least_one_pin_of_each_kind` leaves out the Terraform provider kind, because the repository holds no OpenTofu configuration, and the fixture repository of `tests/research/test_inventory.py` still holds a provider pin
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_rules.py tests/invariants/test_agents_md.py tests/roadmap/implement/test_roadmap_implement_step_rules.py tests/research` passes, and `$ test -z "$(git ls-files tf)"` exits 0

## 3. Point the documents to the infra examples

Kind: other. Reads: `README.md`, `docs/ROUTINE_TASKS.md`, the knowledge base pages. Changes: `README.md`, `docs/ROUTINE_TASKS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/infrastructure_provisioning.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/opentofu_terraform.md`, `src/devops_cli/ai/knowledge_base/it_domains/topics/infrastructure_as_code_and_cloud_automation.md`.

- [x] 3.1 Replace the `tf/README.md` link of `README.md` with a link to the examples of the infra repository. In the three knowledge base pages, use `tf/examples/aws` and a copy of its `aws.tfvars.example` in the command examples, and show the infra layout in the folder trees. In `docs/ROUTINE_TASKS.md`, name only `k8s/` for the IaC scans of this repository
  - Verification: `$ uv run devops ci docs` passes, and `$ test -z "$(git grep -n 'tf/aws\|tf/README' -- README.md src/devops_cli/ai/knowledge_base)"` exits 0

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
