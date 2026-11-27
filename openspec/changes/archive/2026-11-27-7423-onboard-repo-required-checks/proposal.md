# Proposal

## Why

`devops repos onboard` writes the ruleset `main` from the render of the template, with the required checks of the live ruleset and of the template pull request (D3). It never reads the `github/repository.yaml` that the repository holds. So a repository that requires its own checks in that file, such as dan-petty/homelab with `K8s`, `Lint` and `PR title / Semantic PR title`, never gets them from `--confirm`, and `--plan` does not show them. A person added the checks of dan-petty/homelab to the live ruleset by hand on 2026-11-27 (#7423).

## What Changes

- Row 10 reads the `github/repository.yaml` of the default branch of the repository and checks it against the schema of the template at the ref of the baseline.
- For each ruleset of the baseline, the required checks rule of the ruleset of the same name in that file merges into the ruleset: the file wins for each parameter of the rule that it sets and for the entry of each check that it names. A baseline ruleset with no required checks rule gets the rule of the file.
- The required checks of the live ruleset and of the template pull request stay. No source removes a check that another source requires.
- A file that does not load or that the schema refuses makes row 10 `not readable`, with a reason that names the file. A branch with no file keeps the old result.
- `Baseline` keeps the text of the schema, so the row reads the schema one time.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: row 10 requires the checks of the `github/repository.yaml` of the repository.

## Impact

- Code: `src/devops_cli/github/onboard/baseline.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/routes.py` (the read of the dry run).
- Tests: `tests/github/onboard/test_onboard_rows.py`.
- Documents: `docs/repos/onboard.md` (row 10), `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md` (Status History).
- The plan sends one more GET and no write. The change adds only required checks and their rule parameters, so it lowers no other rule of a live ruleset.

## Feasibility

- `src/devops_cli/github/onboard/settings_rows.py`: `ruleset_row` reads only `baseline.settings`, and `_with_required_checks` adds the checks of the live ruleset and of `ctx.reported_checks`.
- `src/devops_cli/github/onboard/baseline.py`: the baseline is the render of the template at the ref; the repository file is not read.
- The `github/repository.yaml` of dan-petty/homelab on `main` requires `K8s`, `Lint` and `PR title / Semantic PR title` with integration 15368 in the ruleset `main`.
- Row 8 reads the `.github/labels.yml` of the default branch of the repository in the same way, so the read has a model in the command.

## Existing Tool Considered

The alternatives check of #7423 gives `partly`: the GitHub provider of OpenTofu (integrations/terraform-provider-github, MIT) can plan and apply required checks, but ADR 0035 gives the repository settings to the command, and the provider never reads `github/repository.yaml`. The change extends row 10: about 40k tokens and 2 hours.

## Dependencies

None. #7318 (a skipped check name) and #7326 (row 10 lowers a stricter live ruleset) change the same row and stay open.
