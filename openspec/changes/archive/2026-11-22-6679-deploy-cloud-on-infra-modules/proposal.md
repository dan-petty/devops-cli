# Proposal: #6679

## Why
Closes #6679. `devops tf deploy-cloud -p <provider>` reads `tf/<provider>` and `tf/environments/<provider>.tfvars.example` under the worktree root of the working folder. dan-petty/infra now holds the cloud cluster modules (`tf/modules/aws-eks`, `azure-aks`, `gcp-gke`) and one example root module for each provider in `tf/examples/<provider>`, with its values in `tf/examples/<provider>/<provider>.tfvars.example` (ADR 0032, infra#9). This repository keeps an older copy of the same configurations in `tf/aws`, `tf/azure`, `tf/gcp` and `tf/environments`. Two copies must not stay live.

## What Changes
- The constants `CONST_TF_AWS_DIR`, `CONST_TF_AZURE_DIR` and `CONST_TF_GCP_DIR` name `tf/examples/<provider>`, the infra layout, below the new `CONST_TF_EXAMPLES_DIR`. `CONST_TF_ENVIRONMENTS_DIR` goes. The default variable file of a provider is `<provider>.tfvars.example` in its example folder.
- `devops tf deploy-cloud` stops with a `ValidationError` when the example folder of the provider does not exist, also in a dry run. The message names the folder and says to run the command in an infra checkout. Before, the dry run planned a folder that did not exist, and the real run failed in `tofu init`.
- `tf/aws`, `tf/azure`, `tf/gcp`, `tf/environments` and `tf/README.md` go. This repository has no `tf/github`, so the `tf/**` route of `src/devops_cli/roadmap/step_rules.py` goes, and the AGENTS.md row "change a manifest, the cluster or OpenTofu" becomes "change a manifest or the cluster".
- `README.md`, three knowledge base pages, `docs/ROUTINE_TASKS.md` and the generated command pages follow the infra layout.
- The command reads other folders and prints a new message, so the change is observable and carries a spec delta.
- The change fits one pull request.

## Capabilities
- `tf-deploy-cloud`: new capability with two ADDED requirements, "Deploy-cloud reads the example of the provider in the infra layout" and "A missing example folder names an infra checkout".

## Impact
- A person runs `devops tf deploy-cloud -p <provider>` in a checkout of the infra repository. In this repository the command stops with the new message.
- The local state of a provider moves with its folder: state in an old `tf/<provider>` folder of a checkout stays there, and `deploy-cloud` does not read it. The infra examples have no backend and no state.
- `src/devops_cli/research/terraform_pins.py` keeps its glob `tf/**/*.tf`, and `roadmap.alternatives.inventory_paths` keeps `tf`, because both read the root of any clone that they get.
- The Renovate terraform manager of the shared preset finds no `.tf` file in this repository. The preset needs no change.

## Feasibility
- infra: PR 29 of dan-petty/infra merged on 2026-11-22. `devops gh api 'repos/dan-petty/infra/contents/tf/examples?ref=main' --jq '.[].path'` gives `tf/examples/README.md`, `aws`, `azure`, `example` and `gcp`. Each of `aws`, `azure` and `gcp` holds `main.tf`, `outputs.tf`, `variables.tf`, `versions.tf`, `.terraform.lock.hcl` and `<provider>.tfvars.example`.
- Code: on origin/main `077428d43`, `_get_cloud_dir` and `_get_default_var_file` of `src/devops_cli/commands/tf.py` join `CONST_TF_<PROVIDER>_DIR` and `CONST_TF_ENVIRONMENTS_DIR` to `find_worktree_root(Path.cwd())`. Nothing checks that the folder exists before the dry run plans it.
- Counts: `git ls-files tf | wc -l` gives 16 files, all in the 5 paths that go. `git grep -n 'CONST_TF_\(AWS\|AZURE\|GCP\|ENVIRONMENTS\)' -- src tests` gives 8 lines in `commands/tf.py` and 11 in `tests/commands/test_tf.py`, outside the definitions. `git grep -c 'tf/aws\|tf/README' -- README.md src/devops_cli/ai/knowledge_base` gives 17 lines in 4 files. `tf/github` does not exist.
- The `tf/**` route is the only route of `ROUTES` with no sections, and `test_a_route_without_sections_gives_the_start_of_its_document_cut_to_the_cap` reads it. That test moves to a route that it builds in a temporary checkout.

## Existing Tool Considered
- The change uses the OpenTofu configurations of dan-petty/infra, which call maintained registry modules (ADR 0032). It builds no tool: it changes 4 path constants, one guard and the documents.
- Build cost: about 40 lines of code and tests, about 60k tokens and 1 hour.
- Deleted internal code: the 16 files under `tf/`, `CONST_TF_ENVIRONMENTS_DIR` and the `tf/**` route of `step_rules.py`.
