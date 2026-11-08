# Tasks

## 1. Extract the shared type label rule

Kind: behavior. Reads: `src/devops_cli/roadmap/intake/intake.py` (lines 568-585), `src/devops_cli/roadmap/title_labels.py`, `tests/roadmap/intake/test_roadmap_intake_title_labels.py`. Changes: `src/devops_cli/roadmap/title_labels.py`, `src/devops_cli/roadmap/intake/intake.py`, `tests/roadmap/test_roadmap_title_labels.py` (new).

- [x] 1.1 In `tests/roadmap/test_roadmap_title_labels.py`, write tests for `declared_type_labels` checking that it returns `type/*` label names other than `type/epic`, and an empty tuple when none match.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_title_labels.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/title_labels.py`, add `declared_type_labels(declared: Collection[str]) -> tuple[str, ...]`. In `src/devops_cli/roadmap/intake/intake.py`, update `types` property to call `declared_type_labels(self.declared)`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_title_labels.py tests/roadmap/intake/test_roadmap_intake_title_labels.py` passes

## 2. Implement check_onboarding, apply_onboarding, and onboard command

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_labels.py`, `src/devops_cli/github/labels.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/support/fakes/github.py`. Changes: `tests/support/fakes/github.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/onboard.py` (new), `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_onboard.py` (new).

- [x] 2.1 In `tests/roadmap/test_roadmap_onboard.py`, write tests for `devops roadmap onboard`:
  - A repository that holds every prerequisite prints six rows and exits 0.
  - When `has_issues` is false, row 1 is `missing` and prints `devops gh api -X PATCH repos/<owner>/<name> -f has_issues=true`, and no request uses `PATCH`.
  - When `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` is absent, row 2 is `not readable as <login>` and makes no request to `/installation/repositories`.
  - When the App key is present, row 2 is `present` when the installation lists the repo, and `missing` when it does not.
  - When `.github/labels.yml` is absent, not YAML, not a list of labels, or has no `type/*` other than `type/epic`, row 3 is `missing` with the matching reason and row 4 is `not readable`.
  - With `--confirm`, missing labels are created with `POST`, no `PATCH` or `DELETE` is sent, and differing labels are kept.
  - A second `--confirm` sends no write.
  - `--dry-run` makes zero requests and renders the request plan.
  - Two mode flags fail with the usage error.
  - Exit code is 1 when any row is `missing`, and 0 otherwise.
  - Row 6 prints `service.repos` line and `devops k8s deploy-stack`, leaving `config.yaml` untouched.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` fails on the base
- [x] 2.2 In `tests/support/fakes/github.py`, add route helper for `/installation/repositories`. In `src/devops_cli/lang/en/help.py` and `messages.py`, add help and messages for onboard. In `src/devops_cli/roadmap/request_plan.py`, add `onboard_requests`. In `src/devops_cli/roadmap/onboard.py`, implement `check_onboarding`, `apply_onboarding`, and rendering. In `src/devops_cli/commands/roadmap.py`, add the `onboard` command.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 3. Document the onboard command

Kind: documents. Reads: `README.md`, `docs/roadmap/inbox.md`. Changes: `docs/roadmap/onboard.md` (new), `README.md`, `docs/commands/roadmap.md`.

- [x] 3.1 Create `docs/roadmap/onboard.md` documenting `devops roadmap onboard` in ASD-STE100, and run `uv run devops docs generate --sync-readme` to sync `README.md` and `docs/commands/roadmap.md`.
  - Verification: `$ uv run devops docs check` passes

## Criteria

- Group 1: The `type/*` rule SHALL live in one function in `src/devops_cli/roadmap/title_labels.py`, and intake and onboard SHALL both call it.
- Group 2: The `onboard` command SHALL print one row for each of the six prerequisites, and each row SHALL hold one state: `present`, `missing`, or `not readable` with its reason.
- Group 2: When `has_issues` is false, the command SHALL set row 1 to `missing` and SHALL print the `devops gh api -X PATCH` command, and it MUST NOT send a `PATCH`.
- Group 2: Without the App private key in the environment, the command SHALL set row 2 to `not readable as <login>` and MUST NOT send a request to `/installation/repositories`.
- Group 2: With the App private key in the environment, the command SHALL set row 2 to `present` when `GET /installation/repositories` lists the repository, and to `missing` when it does not.
- Group 2: The command SHALL set row 3 to `missing` with the reason when `.github/labels.yml` is absent, is not YAML, is not a list of labels, or declares no `type/*` label other than `type/epic`, and it SHALL set row 4 to `not readable`.
- Group 2: `--confirm` SHALL send one `POST` to `repos/<owner>/<name>/labels` for each declared label that GitHub lacks, and it MUST NOT send a `PATCH` or a `DELETE` for any label.
- Group 2: A second `--confirm` after a successful one SHALL send no write.
- Group 2: `--dry-run` SHALL make no request and SHALL print the read endpoints and the possible writes with placeholders.
- Group 2: The command SHALL refuse two mode flags with the usage error that the other roadmap commands use, and `--plan` SHALL send no write.
- Group 2: The command SHALL exit 1 when a row is `missing`, and 0 when every row is `present` or `not readable`.
- Group 2: Row 6 SHALL print the `service.repos` line and the `devops k8s deploy-stack` step when the repository is absent from the setting, and the command MUST NOT write `config.yaml`.
- Group 3: `docs/roadmap/onboard.md` SHALL document the command, and the README command list SHALL link it.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
