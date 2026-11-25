# tf-deploy-cloud Specification

## Purpose
How `devops tf deploy-cloud` finds the OpenTofu example of a cloud provider in an infra checkout, which variable file it uses by default, and what it says when the working folder holds no example.

## Requirements

### Requirement: Deploy-cloud reads the example of the provider in the infra layout

`devops tf deploy-cloud --provider <provider>` SHALL use the folder `tf/examples/<provider>` under the worktree root of the working folder as its OpenTofu configuration, for the providers `aws`, `azure` and `gcp`. When `--var-file` is not given and `tf/examples/<provider>/<provider>.tfvars.example` exists, the command SHALL use that file as its variable file.

#### Scenario: A dry run in an infra checkout

- **WHEN** `devops tf deploy-cloud --provider aws --dry-run` runs in a checkout that holds `tf/examples/aws/aws.tfvars.example`
- **THEN** the command exits 0, prints the folder `tf/examples/aws` of the checkout, plans `tofu init` and `tofu apply -var-file <checkout>/tf/examples/aws/aws.tfvars.example`, and starts no process

#### Scenario: An example with no variable file

- **WHEN** the default variable file of `azure` is looked up in a checkout whose `tf/examples/azure` holds no `azure.tfvars.example`
- **THEN** the lookup gives no file

### Requirement: A missing example folder names an infra checkout

When `tf/examples/<provider>` does not exist under the worktree root of the working folder, `devops tf deploy-cloud --provider <provider>` SHALL exit 1 before it plans or starts a command, with or without `--dry-run`. Its error line SHALL name the missing folder and say to run the command in an infra checkout.

#### Scenario: Deploy-cloud in a checkout with no examples

- **WHEN** `devops tf deploy-cloud --provider aws` runs, with and without `--dry-run`, in a checkout that has no `tf/examples/aws`
- **THEN** the command exits 1, prints the missing folder and the words "infra checkout", and starts no process
