# Tasks

## 1. Ask for administration read in the installation token

Reads: `src/devops_cli/github/app_installation.py`, `tests/github/test_github_app_identity.py`. Changes: `src/devops_cli/config/constants.py`, `tests/github/test_github_app_identity.py`.

- [ ] 1.1 `test_the_token_request_asks_only_for_the_permissions_the_roadmap_jobs_use` in `tests/github/test_github_app_identity.py` fails once its `ROADMAP_PERMISSIONS` gains `administration: read`, because the request body still names seven permissions
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` fails on the base
- [ ] 1.2 Add the entry `administration` at level `read` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS` in `src/devops_cli/config/constants.py`, and name the traffic reads in the comment above it. Add the same entry to `ROADMAP_PERMISSIONS` in `tests/github/test_github_app_identity.py`, so the test reads the body of the exchange with eight permissions
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` passes

## 2. Read the traffic of the App and name the missing permission

Reads: `src/devops_cli/core/process.py`, `tests/support/fakes/github_repository.py`. Changes: `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics.py`, `tests/roadmap/test_roadmap_run_metrics.py`.

- [ ] 2.1 `test_the_app_asks_the_four_traffic_endpoints` in `tests/github/test_github_metrics.py` fails, because `get_repository_traffic_metrics` sends no traffic request when the process acts as the App. `test_a_path_that_the_token_cannot_read_is_asked_once` fails, because it expects one debug line and no warning that names `administration: read`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/roadmap/test_roadmap_run_metrics.py` fails on the base
- [ ] 2.2 Drop `acts_as_github_app()` from the guard of `get_repository_traffic_metrics`, drop it from the import of `devops_cli.core.process`, keep the test on the refused set of repositories, and rewrite the docstring. Replace the debug line with one warning that names the repository and `administration: read`. In `tests/github/test_github_metrics.py`, replace `test_the_app_asks_no_traffic_endpoint_and_says_so` with `test_the_app_asks_the_four_traffic_endpoints`, which asserts the four calls, `traffic_collected` true and the `repo` label of each traffic point; give the fake a refusal in `test_a_report_without_traffic_sends_no_traffic_series`; change `test_a_path_that_the_token_cannot_read_is_asked_once` to expect one warning that names `administration: read`, no debug line and no traffic request in the second collection; and answer the four traffic paths with the 403 refusal in `test_the_command_prints_that_the_app_collected_no_traffic`. In `tests/roadmap/test_roadmap_run_metrics.py`, change `test_the_metrics_job_of_the_app_asks_no_traffic_endpoint` to expect the four calls, no traffic series and the warning
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/roadmap/test_roadmap_run_metrics.py` passes

## 3. Record the permission in ADR 0015

Reads: `src/devops_cli/config/constants.py`. Changes: `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`.

- [ ] 3.1 Add an amendment line dated 2026-11-11 that names `administration: read` and issue 4757, in the shape of the `workflows: write` line. Add the permission to the list of the decision bullet that names the token's permissions. Replace the consequence sentence that says the metrics row asks for no traffic, so the record matches the token that each job mints, and run this check by hand: Open `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md` and read the amendment lines: one line dated 2026-11-11 names `administration: read` and issue 4757. Read the decision bullet that lists the token's permissions: it names eight permissions, `administration` at read included. Read the consequence paragraph that names the traffic endpoints: it says the metrics row reads the traffic and no longer says that the row asks for none. Repeat the read on the merged file after any later edit of the record.
- [ ] 3.2 Edit `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md` and add the amendment line, the permission of the decision bullet and the corrected consequence
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: the token request of the metrics job holds `administration: read`.
- Group 2: A test: a process that acts as the App reads the four traffic endpoints through the GitHub fake and emits the traffic gauges with the repo label.
- Group 2: A test: a 403 answer for one repository puts it in the refused set and logs the missing permission, and the next round does not read its traffic.
- Pending person: Live, 1 h after the rollout: `last_over_time(devops_cli_project_traffic_views{job='roadmap-service'}[1h])` has one series for each repository of `service.repos`, and the devops-cli value equals the count of `GET /repos/{owner}/{repo}/traffic/views`., Only a person can read the live Prometheus series and the GitHub traffic count one hour after the rollout, and this run holds no cluster and no network.
- Group 3: If the shared permission set changes, ADR 0015 names the permission.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
