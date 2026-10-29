# tf-lint Specification

## Purpose
The `devops tf lint` command lints Terraform and OpenTofu files with the tflint that `tools.lock` pins. It never reports a pass when tflint did not run.

## Requirements

### Requirement: A lint that did not run is no pass
When tflint did not run, the `devops tf lint` command SHALL exit 1 and say that the lint did not run, in each output format. It SHALL give the status and the reason of the scan. It SHALL NOT say that no issue was detected.

#### Scenario: tflint is not on the path
- **WHEN** `devops tf lint <directory>` runs and no directory of PATH holds tflint
- **THEN** the command says that the TFLint lint is `unavailable` because `Binary 'tflint' not found on PATH`, says no pass, and exits 1

#### Scenario: tflint is not on the path and the format is JSON
- **WHEN** `devops tf lint <directory> --json` runs and no directory of PATH holds tflint
- **THEN** the command exits 1 and prints no findings list

### Requirement: A clean lint passes
The `devops tf lint` command SHALL say that no issue was detected only when tflint ran and reported no issue, and SHALL then exit 0.

#### Scenario: tflint finds nothing
- **WHEN** `devops tf lint <directory>` runs, and tflint writes `{"issues": [], "errors": []}` and exits 0
- **THEN** the command says that no Terraform / OpenTofu lint issue was detected and exits 0
