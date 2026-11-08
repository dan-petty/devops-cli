# Proposal

## Why

#1359: The roadmap jobs and the roadmap Service (`devops serve --service`) manage a repository only when some prerequisites hold. No command checks them, so a person finds each missing one when a job fails. This change gives that person one command, `devops roadmap onboard [--repo owner/name]`, that lists every missing prerequisite and creates the labels that the repository lacks.

## What Changes

- Add the command `devops roadmap onboard [--repo owner/name]`. Without `--repo`, it uses the origin of the checkout, as other roadmap commands do.
- Check six prerequisites and print one row for each:
  1. Issues are turned on (`GET repos/<owner>/<name>`, field `has_issues`). When missing, print `devops gh api -X PATCH repos/<owner>/<name> -f has_issues=true`. Never run it.
  2. The App `devops-cli-service` is installed on the repository. When the environment holds `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, read `GET /installation/repositories` through `GitHubSession.paginate`. The row is `present` when the list holds the repository and `missing` when it does not. In every other case, report `not readable as <login>` and send no request to `/installation/repositories`.
  3. `.github/labels.yml` is on the default branch, is valid YAML, is a list of label specs, and declares a `type/*` label other than `type/epic`. When invalid or absent, report `missing` with the matching reason.
  4. Every label of that file exists on GitHub. When row 3 is not `present`, row 4 is `not readable`. With `--confirm`, create each missing label with `POST repos/<owner>/<name>/labels`. A label with another color or description is kept and never edited.
  5. `.github/workflows/clear-status.yml` is on the default branch.
  6. The repository is in `service.repos` in the local settings. When absent, print the line to add to `config.yaml` and `devops k8s deploy-stack`. Never write `config.yaml`.
- Modes:
  - `--dry-run`: makes no request and prints the read endpoints and possible writes with placeholders.
  - `--plan`: reads and prints the rows and writes nothing. A run with no mode flag does the same and prints a note.
  - `--confirm`: reads, creates missing labels of row 4, and prints the steps of rows 1, 2, and 6. A second `--confirm` right after the first sends no write.
- The command exits 1 when a row is `missing`, and 0 when every row is `present` or `not readable`.
- Move the `type/*` rule out of the `types` property in `src/devops_cli/roadmap/intake/intake.py` into `declared_type_labels` in `src/devops_cli/roadmap/title_labels.py`. Intake and onboard both call it.
- Add `docs/roadmap/onboard.md` and document the command in `README.md`.
- The change fits one pull request. It has observable changes to the CLI interface and messages, so it carries a spec delta in `roadmap-onboard`.

## Capabilities

### New Capabilities

- `roadmap-onboard`: Purpose and requirements for the `devops roadmap onboard` command checking repository prerequisites and creating missing labels.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/title_labels.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_onboard.py`, `tests/support/fakes/github.py`.
- Documentation: `docs/roadmap/onboard.md`, `README.md`, `docs/commands/roadmap.md`.

## Existing code

- Reuse `declared_specs` in `src/devops_cli/roadmap/pull_labels.py`.
- Reuse `diff_labels` and `LabelSpec` in `src/devops_cli/github/labels.py`.
- Reuse `RoadmapStore.repository_file` and `RoadmapStore.repository_labels`.
- Reuse `GitHubSession.rest` and `GitHubSession.paginate`.
- Reuse `render_dry_run` and `StoreRequests` in `src/devops_cli/roadmap/request_plan.py`.
- Reuse `_one_mode` in `src/devops_cli/commands/roadmap.py`.

## Acceptance

Each acceptance criterion of #1359 maps to tasks in `tasks.md`.

| Criterion of the issue | Delivered by |
| :--- | :--- |
| One row for each prerequisite with state present, missing, or not readable | Group 2 |
| Issues setting printed and never written | Group 2 |
| App row without App key reads not readable as login and makes no request | Group 2 |
| App row as App reads present or missing from installation listing | Group 2 |
| Invalid labels file makes row 3 missing and row 4 not readable | Group 2 |
| Labels created and never edited; differing label kept | Group 2 |
| Second confirm sends no write | Group 2 |
| Dry run makes no request and prints request plan | Group 2 |
| One mode flag at a time | Group 2 |
| Exit code 1 when a row is missing, 0 otherwise | Group 2 |
| Row 6 prints service.repos line and deploy-stack command, no config edit | Group 2 |
| One copy of type/* rule in title_labels.py | Group 1 |
| Command documented in docs/roadmap/onboard.md and README.md | Group 3 |

## Feasibility

Checked on origin/main at c8990bed:
- `GET repos/<owner>/<name>` returns `has_issues` as a boolean.
- `GET /installation/repositories` returns a JSON object with `repositories` as an array of repositories.
- `GitHubSession.paginate("/installation/repositories", iterable_key="repositories")` reads each page.
- `declared_specs` reads `.github/labels.yml` on the default branch.
- `diff_labels` partitions labels into `(to_create, to_update, unchanged)`.
- `acts_as_github_app()` in `src/devops_cli/core/process.py` checks `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`.
- All prerequisites and edge cases can be tested offline with `GitHubApiFake`.

## Existing Tool Considered

No open, maintained tool covers the onboarding check: a label-sync tool also edits labels, and this command must only create them, while `diff_labels` already provides the create-only diff. gidgethub, the project GitHub library, covers every read and write through `GitHubSession.rest` and `GitHubSession.paginate`, so the change adds no HTTP code. Written cost: about 45,000 tokens to build, about 10,000 tokens a month to maintain, and about one working day. The change deletes no internal code outside consolidating the `type/*` rule.
