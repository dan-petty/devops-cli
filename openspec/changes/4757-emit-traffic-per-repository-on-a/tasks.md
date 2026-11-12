# Tasks

## 1. Ask for administration read in the installation token

Reads: `src/devops_cli/github/app_installation.py`, `tests/github/test_github_app_identity.py`. Changes: `src/devops_cli/config/constants.py`, `tests/github/test_github_app_identity.py`.

- [x] 1.1 Add `administration: read` to `ROADMAP_PERMISSIONS` in `tests/github/test_github_app_identity.py`, and add `administration (read)` to the HTTP 422 message of `test_an_installation_without_a_requested_permission_fails_naming_the_permissions`. The token request tests and the 422 test fail, because the request body still names seven permissions
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` fails on the base
- [x] 1.2 Add the entry `administration` at level `read` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS` in `src/devops_cli/config/constants.py`, and name the traffic reads in the comment above it
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` passes

## 2. Read the traffic of the App and name the missing permission

Reads: `src/devops_cli/core/process.py`, `tests/support/fakes/github_repository.py`. Changes: `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics.py`, `tests/roadmap/test_roadmap_run_metrics.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_run_metrics.py`, replace `test_the_metrics_job_of_the_app_asks_no_traffic_endpoint` with `test_the_metrics_job_of_the_app_sends_the_traffic_of_the_repository`, which expects the four traffic calls, the views and the stars with the `repo` label, and no warning. In `tests/github/test_github_metrics.py`, change `test_a_path_that_the_token_cannot_read_is_asked_once` to expect one warning that names `example/repo` and `administration: read`, and no debug line. Both fail on the base
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/roadmap/test_roadmap_run_metrics.py` fails on the base
- [x] 2.2 Drop `acts_as_github_app()` from the guard of `get_repository_traffic_metrics` and from the import of `devops_cli.core.process`, keep the refused set of repositories, and rewrite the docstring. Replace the debug line with one warning that names the repository and `administration: read`. In `tests/github/test_github_metrics.py`, remove the `app` flag of the `_github` helper and `test_the_app_asks_no_traffic_endpoint_and_says_so`, give the fake the refusal in `test_a_report_without_traffic_sends_no_traffic_series`, and answer the four traffic paths with the refusal in `test_the_command_prints_that_the_traffic_was_not_collected`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/roadmap/test_roadmap_run_metrics.py` passes

## 3. Record the permission in ADR 0015 and TELEMETRY.md

Reads: `src/devops_cli/config/constants.py`. Changes: `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [x] 3.1 Add an amendment line dated 2026-11-12 that names `administration: read` and issue 4757, in the shape of the `workflows: write` line. Add the permission to the decision bullet that names the token's permissions. Replace the consequence sentence that says the metrics row asks for no traffic. Check by hand: the amendment line names `administration: read` and #4757, the decision bullet names Administration read, and the consequence paragraph says that each token asks for it
- [x] 3.2 Replace the paragraph of the generator that says the Service sends no traffic gauge, and write `docs/TELEMETRY.md` again from it
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: the token request of the metrics job holds `administration: read`.
- Group 2: A test: a process that acts as the App reads the four traffic endpoints through the GitHub fake and emits the traffic gauges with the repo label.
- Group 2: A test: a 403 answer for one repository puts it in the refused set and logs the missing permission, and the next round does not read its traffic.
- Pending person: Live, 1 h after the rollout: `last_over_time(devops_cli_project_traffic_views{job='roadmap-service'}[1h])` has one series for each repository of `service.repos`, and the devops-cli value equals the count of `GET /repos/{owner}/{repo}/traffic/views`., Only a person can read the live Prometheus series and the GitHub traffic count one hour after the rollout, and this run holds no cluster and no network.
- Group 3: If the shared permission set changes, ADR 0015 names the permission.

## Workflow follow-up

- Pending a person: before the merge, run the premise probe of the pull request comment: a token that asks for `administration: read` gets HTTP 200 from the four traffic paths.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
