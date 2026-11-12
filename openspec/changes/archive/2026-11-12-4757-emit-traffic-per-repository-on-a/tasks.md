# Tasks

## 1. Ask for administration read in the installation token

Reads: `src/devops_cli/github/app_installation.py`, `tests/github/test_github_app_identity.py`. Changes: `src/devops_cli/config/constants.py`, `tests/github/test_github_app_identity.py`.

- [x] 1.1 Add `administration: read` to `ROADMAP_PERMISSIONS` in `tests/github/test_github_app_identity.py`, and add `administration (read)` to the HTTP 422 message of `test_an_installation_without_a_requested_permission_fails_naming_the_permissions`. The token request tests and the 422 test fail, because the request body still names seven permissions
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` fails on the base
- [x] 1.2 Add the entry `administration` at level `read` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS` in `src/devops_cli/config/constants.py`, and name the traffic reads in the comment above it
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` passes
- [x] 1.3 In `test_a_reply_that_grants_more_keeps_the_token_and_logs_only_the_permission_names`, grant `pages: write` in place of `administration: write`, because the request now names `administration`, and expect `pages` in the log
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py` passes

## 2. Read the traffic of the App and name the missing permission

Reads: `src/devops_cli/core/process.py`, `tests/support/fakes/github_repository.py`. Changes: `src/devops_cli/github/metrics.py`, `tests/github/test_github_metrics.py`, `tests/roadmap/test_roadmap_run_metrics.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_run_metrics.py`, replace `test_the_metrics_job_of_the_app_asks_no_traffic_endpoint` with `test_the_metrics_job_of_the_app_reads_the_traffic_of_the_repository`. When GitHub answers, it expects the four traffic calls, the views and the stars with the `repo` label, and no warning. When GitHub refuses, it expects the stars, no traffic series and one warning that names `administration: read`. In `tests/github/test_github_metrics.py`, change `test_a_path_that_the_token_cannot_read_is_asked_once` to expect one warning that names `example/repo` and `administration: read`, and no debug line. Both fail on the base
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/roadmap/test_roadmap_run_metrics.py` fails on the base
- [x] 2.2 Drop `acts_as_github_app()` from the guard of `get_repository_traffic_metrics` and from the import of `devops_cli.core.process`, keep the refused set of repositories, and rewrite the docstring. Replace the debug line with one warning that names the repository and `administration: read`. In `tests/github/test_github_metrics.py`, remove the `app` flag of the `_github` helper and `test_the_app_asks_no_traffic_endpoint_and_says_so`, give the fake the refusal in `test_a_report_without_traffic_sends_no_traffic_series`, and answer the four traffic paths with the refusal in `test_the_command_prints_that_the_traffic_was_not_collected`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/roadmap/test_roadmap_run_metrics.py` passes

## 3. Record the permission in ADR 0015 and TELEMETRY.md

Reads: `src/devops_cli/config/constants.py`. Changes: `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`, `tests/docs/test_docs.py`.

- [x] 3.1 Add an amendment line dated 2026-11-12 that names `administration: read` and issue 4757, in the shape of the `workflows: write` line. Add the permission to the decision bullet that names the token's permissions. Add `repository_hooks` and `administration` to the gidgethub bullet. Replace the consequence sentence that says the metrics row asks for no traffic, and replace the rule that a feature with more permissions asks for a token with its own set with the shared-set rule and the person check of the grant. Check by hand: the amendment line names `administration: read` and #4757, the decision and gidgethub bullets name it, and the consequence paragraph names the shared set, what Administration read can read and the person check
- [x] 3.2 Replace the paragraph of the generator that says the Service sends no traffic gauge, write `docs/TELEMETRY.md` again from it, and change `test_doc_generator_telemetry_docs` in `tests/docs/test_docs.py` to find the new paragraph once and the old sentence never
  - Verification: `$ uv run devops ci docs` passes

## 4. Correct the App setup and the traffic panels

Reads: `docs/TELEMETRY.md`. Changes: `k8s/README.md`, `k8s/monitoring/dashboards/project-metrics.json`, `tests/prometheus/test_k8s_monitoring_dashboards.py`.

- [x] 4.1 Replace `test_each_traffic_panel_names_the_workstation_command_that_sends_its_numbers` with `test_each_traffic_panel_names_the_senders_of_its_numbers`. It expects that each traffic panel says that the roadmap Service and `devops gh metrics --emit-telemetry` send traffic numbers, and that a repository whose traffic GitHub refused has no traffic series. It fails on the base
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` fails on the base
- [x] 4.2 Change the description of the panels 16, 17, 19 and 20 of `project-metrics.json` to that text, and add Administration read to the permissions of step 1 of the Roadmap service setup in `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## Criteria

- Group 1: A test: the token request of the metrics job holds `administration: read`.
- Group 2: A test: a process that acts as the App reads the four traffic endpoints through the GitHub fake and emits the traffic gauges with the repo label.
- Group 2: A test: a 403 answer for one repository puts it in the refused set and logs the missing permission, and the next round does not read its traffic.
- Pending person: Live, 1 h after the rollout: `last_over_time(devops_cli_project_traffic_views{job='roadmap-service'}[1h])` has one series for each repository of `service.repos`, and the devops-cli value equals the count of `GET /repos/{owner}/{repo}/traffic/views`., Only a person can read the live Prometheus series and the GitHub traffic count one hour after the rollout, and this run holds no cluster and no network.
- Group 3: If the shared permission set changes, ADR 0015 names the permission.

## Workflow follow-up

- Pending a person: before the merge, confirm on the installation page of App `devops-cli-service` that Administration is granted (read, or read and write) and that no permission request waits. If it is not granted, do not merge: GitHub would refuse each token of each job with HTTP 422.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
