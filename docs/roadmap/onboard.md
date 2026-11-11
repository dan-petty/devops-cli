# Repository onboarding

`devops roadmap onboard` checks a repository against the six prerequisites of the roadmap jobs. The command help gives a summary only. This page gives the rest.

## Prerequisites

The command checks six prerequisites in this order:

1. **Issues are turned on.** GitHub must enable the issues feature for the repository (`has_issues: true`). When missing, the command outputs the `devops gh api -X PATCH` command that a person can run. The command itself never patches the repository.
2. **The App devops-cli-service is installed on the repository.** When the process acts as the App, the command checks whether the repository is in the installation (`GET /installation/repositories`). When the process acts as a user, the command reports `not readable as <login>` and sends no installation request.
3. **`.github/labels.yml` is on the default branch, is valid, and declares a `type/*` label other than `type/epic`.** The file must exist, must be valid YAML, must list labels with name and color, and must declare at least one `type/*` label that is not `type/epic`.
4. **Every label of that file exists on GitHub.** When row 3 is missing or not readable, row 4 is not readable. When row 3 is present, the command compares declared labels with repository labels. Differing labels are listed and kept.
5. **`.github/workflows/clear-status.yml` is on the default branch.** The workflow file must exist on the default branch.
6. **The repository is in `service.repos`.** Local configuration must include the repository in `service.repos`. When missing, the command outputs the line for `config.yaml` and the stack deployment command. The command never edits `config.yaml`.

## Output and exit code

Each row shows its number, description, state (`present`, `missing`, or `not readable`), and optional reason or next step:

- When every row is `present` or `not readable`, the command exits with code 0.
- When any row is `missing`, the command exits with code 1.
- Output ends with the count of rows that are not readable.

## Modes

The command supports four modes:

- **Default**: Runs the check and prints a note that `--confirm` creates missing labels.
- `--plan`: Runs the check with no write.
- `--confirm`: Runs the check and creates missing labels on GitHub with `POST repos/<owner>/<name>/labels`. Differing labels are kept. No label is patched or deleted.
- `--dry-run`: Makes zero requests to GitHub and renders the planned reads and writes.

You can pass at most one mode flag at a time.

## A missing dependency that a job finds

A Service row can find a project-management dependency that the repository lacks. The stage job reads `openspec/config.yaml` at the default branch in each round (`uses_openspec`). With no file, it writes no plan for an item of the repository, and each item gets a reason that names the file. The stage row also names the file in its outcome (`JobOutcome.missing`), which the later rows of the round read. A later row can start the onboarding of the repository from this record (#4664). #3770 makes onboarding add `openspec/config.yaml`. The hold ends when the file is on the default branch.
