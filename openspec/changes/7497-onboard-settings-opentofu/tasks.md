# Tasks

## 1. Record the decision

Kind: documents. Reads: `docs/adr/README.md`, `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md`. Changes: `docs/adr/0041-opentofu-holds-the-repository-settings.md` (new), `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, `docs/adr/README.md`.

- [x] 1.1 Write ADR 0041 with `status: proposed` and `amends: ["0026", "0032"]`, add `"0041"` to `amended-by` of ADR 0026 and ADR 0032 with their dated `Status History` lines, and regenerate the index
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [x] 1.2 Check the generated documents
  - Verification: `$ uv run devops docs check`
- [ ] 1.3 When the owner accepts the decision, in this pull request: set `supersedes: ["0035"]` on ADR 0041, `status: superseded`, `superseded-by: ["0041"]` and the `Status History` line on ADR 0035, and `status: accepted` with `body-hash` on ADR 0041. Change each citation of ADR 0035 in `src/devops_cli/config/defaults.py`, `src/devops_cli/github/onboard/__init__.py`, `src/devops_cli/github/onboard/drift.py`, `src/devops_cli/github/onboard/routes.py` and `tests/github/onboard/test_onboard_routes.py` to ADR 0041. Change row ACC-3 of `docs/guidelines/production-readiness.md` to the roots of ADR 0041, and its entry in `READINESS_ROWS` of `src/devops_cli/roadmap/project_review/readiness.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py tests/invariants/test_adr_superseded_citations.py tests/roadmap/project_review/test_readiness.py`

## 2. Take the rows of OpenTofu out of the command

Kind: behavior. Reads: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`, `tests/support/github_repository.py`. Changes: the same files, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/test_onboard_routes.py`, `tests/commands/test_repos_onboard.py`.

- [ ] 2.1 Write the failing tests first. In `tests/commands/test_repos_onboard.py`: `--only 1`, `--only 2` and `--only 5` exit 2 with a message that names `tf/github/<owner>`, and `--create` and `--visibility` are unknown options. In `tests/github/onboard/test_onboard_rows.py`: a plan of a repository that the fake does not hold makes row 0 `failed` with the person step that names the root and the apply of the owner, and sends no write; a `--confirm` of an onboarded repository prints no row 1, 2 or 5. In `tests/github/onboard/test_onboard_routes.py`: `_OTHER_OWNERS` names the routes of OpenTofu (`POST /user/repos`, `PATCH /repos/{owner}/{repo}`, `/environments/`, `/vulnerability-alerts`, `/actions/permissions/workflow` and `PUT /rulesets/{id}`), and no route of `ROUTES` matches one
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py tests/github/onboard/test_onboard_rows.py tests/github/onboard/test_onboard_routes.py` fails on the base
- [ ] 2.2 Delete rows 1, 2 and 5 from `ROW_NAMES` and the run order, and keep the numbers of the other rows. Delete `create_row`, `repository_row`, `environment_row`, their helpers and constants, their routes and their reads. Make `--only` refuse a deleted number. Delete the options `--create` and `--visibility` and their help. Give row 0 the person step for a missing repository. Delete the tests of the deleted rows
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py tests/github/onboard/test_onboard_rows.py tests/github/onboard/test_onboard_routes.py`
- [ ] 2.3 Regenerate the reference of the command
  - Verification: `$ uv run devops docs generate`

## 3. Keep only the calls that the provider cannot hold

Kind: behavior. Reads: `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/baseline.py`, `src/devops_cli/github/onboard/ruleset_merge.py`, `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/drift.py`. Changes: the same files, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/test_onboard_ruleset_merge.py` (deleted), `tests/commands/test_repos_onboard.py`, `tests/support/github_repository.py`.

- [ ] 3.1 Write the failing tests first in `tests/github/onboard/test_onboard_rows.py`: a `--confirm` of a repository with immutable releases off sends one `PUT /repos/<repo>/immutable-releases` and no request to `vulnerability-alerts` or `actions/permissions/workflow`; a repository with no ruleset `quality` gets one `POST /repos/<repo>/rulesets` with the name `quality` and the one rule `code_quality`; a repository with a ruleset `quality` of other parameters gets no write and row 10 is `present`; no run sends a write to a ruleset named `main`; a second `--confirm` sends no write. In `tests/commands/test_repos_onboard.py`, the drift scenarios use a repository with immutable releases off in place of one that allows merge commits
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py tests/commands/test_repos_onboard.py` fails on the base
- [ ] 3.2 Make row 3 compare and write only private vulnerability reporting, immutable releases and the default setup, each with a code comment that names its upstream item (#2399, #2746, pull request #3315). Keep row 4 and give it the comment of #2877. Make row 10 the create-only row of ruleset `quality` with the comment of #3664. Each row compares its own value with the live value
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py tests/commands/test_repos_onboard.py`
- [ ] 3.3 Delete `differences`, `held_differences`, `_list_matches` and `change_lines` of `model.py`, the file `ruleset_merge.py` and its tests, `_checked_settings`, `read_repository_settings`, `SETTINGS_FILE` and `_SCHEMA_PATH` of `baseline.py`, and the check names that row 9 records for row 10. Write the deleted and added lines of `git diff --stat` in the pull request body, against the estimate of design D8
  - Verification: `$ uv run devops ci test tests/github/onboard/ tests/commands/test_repos_onboard.py`
- [ ] 3.4 Prove that no deleted part stays
  - Verification: `$ ! git grep -n ruleset_merge -- src tests`, `$ ! git grep -n held_differences -- src tests`, `$ ! git grep -n read_repository_settings -- src tests`, `$ ! git grep -n -F github-repository.schema.json -- src tests`, `$ ! git grep -n -F /user/repos -- src/devops_cli/github/onboard tests/github/onboard tests/support/github_repository.py`
- [ ] 3.5 Check the types and the lint of the changed code
  - Verification: `$ uv run mypy src/devops_cli/github/onboard src/devops_cli/commands/repos.py`

## 4. Run the drift Job on the rows that stay

Kind: manifests. Reads: `k8s/devops/cronjob-repos-drift.yaml`. Changes: `k8s/devops/cronjob-repos-drift.yaml`.

- [ ] 4.1 Set the arguments of CronJob `repos-drift` to `--only 0,3,4,6,7,8,9,10,11`, and change its comment to name ADR 0041 and the rows that stay
  - Verification: `$ uv run devops ci --check --only k8s`

## 5. Correct the documents

Kind: documents. Reads: `docs/repos/onboard.md`, `docs/CLUSTER.md`, `docs/commands/repos.md`, `k8s/README.md`, `README.md`. Changes: the same files.

- [ ] 5.1 Change the row table and the modes of `docs/repos/onboard.md`, the drift Job of `docs/CLUSTER.md` and `k8s/README.md`, and `docs/commands/repos.md`: a new repository starts with an entry in `tf/github/<owner>` of dan-petty/infra (or `tf/github/<owner>-private` of dan-petty/homelab) and the apply that the owner approves, then the command runs the rows that stay
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #7534: `devops gh api` refuses an agent's review of a pending deployment, before the first apply.
- dan-petty/infra#240: the module `tf/modules/github-repository` with `tofu test` (mock provider), `tflint`, `trivy config` and a release (design D1 to D4).
- dan-petty/homelab#642: the runner scale set of infra and its access to `tofu-state` (design D7).
- dan-petty/infra#241: the public root `tf/github/dan-petty`, its checks and its workflow: the plan comment on a pull request, and the apply in environment `github-settings` (design D7).
- dan-petty/infra#242: the import of the probe dan-petty/dotfiles.
- dan-petty/infra#243: the import of the other public repositories, devops-cli last.
- dan-petty/homelab#643: the private root `tf/github/dan-petty-private`, applied by the job of dan-petty/infra#241.
- dan-petty/homelab#359: the CI check of the private root, with `tflint`, `trivy config` and the secret check of design D6.
- dan-petty/homelab#523: the read-only identity of the drift job for namespace `tofu-state`.
- #5328: the drift job runs `tofu plan -detailed-exitcode -lock=false` on each root with the token of `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS` (design D7).
- dan-petty/github-workflows#11: delete `templates/repository/github/repository.yaml.jinja`, `templates/github-repository.schema.json` and the questions `required_checks` and `code_coverage`, after the build pull request of this change.
- #5325, dan-petty/infra#175 and dan-petty/infra#188: the Pages site, `github-pages` and the collaborators of devops-cli go into the public root.
- dan-petty/homelab#360: the roots of retric-ai, split by visibility as for dan-petty.
- Pending a person: the owner judges Trivy-config GIT-0001 ("Repository is public", CRITICAL) for each public repository of the root.
- Pending a person: the owner creates the App `devops-settings-writer`, environment `github-settings` of infra with the owner as the required reviewer and the branch policy `main`, the secrets of the two Apps, and the fork approval `all_external_contributors` of infra (dan-petty/infra#241).
- Pending a person: the owner runs the one-time script that creates ruleset `quality` from the `code_quality` and `code_coverage` rules of each live `main` ruleset (design D5).
- Pending a person: the owner approves the apply of each import in `github-settings` after its plan comment says `N to import, 0 to add, 0 to change, 0 to destroy` (design D9).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
