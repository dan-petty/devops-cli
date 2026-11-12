# Proposal: #5058

## Why
Each installation token of the App asks for `repository_hooks: read` (#5017) and `administration: read` (#4757), the token of a runner Job included (#5058). Only the `metrics` row of the Service reads the hooks and the traffic. A step of a runner Job runs shell commands that a model writes, and the token is in the environment of each `git` or `gh` child of the job. So a prompt injection in a step can read the configuration of each hook, its URL `hooks.<domain>` included, the deliveries of each hook with their payloads and response headers, and the settings of the repository, such as rulesets, deploy keys and self-hosted runners.

## What Changes
- `CONST_GITHUB_APP_TOKEN_PERMISSIONS` holds the permissions of the roadmap jobs, with no `repository_hooks` and no `administration`.
- The new constant `CONST_GITHUB_APP_METRICS_TOKEN_PERMISSIONS` holds `repository_hooks: read` and `administration: read`, the permissions of the `metrics` row.
- A token request that names no repository, as the Service sends, asks for both sets. A token request that names one repository (`service.github_app.token_repository`, set on each runner Job) asks for the permissions of the roadmap jobs only.
- The HTTP 422 error names the permissions of the token that the process asked for.
- ADR 0015 gets an amendment line, and its permission list, its token request and its risk paragraph state the two sets. `k8s/README.md` (setup step 1, Webhook route) and the docstring of the traffic reader follow.
- The installation token of a runner Job changes, which is the behavior of a Job, so the change has a spec delta.
- The change fits one pull request.

## Capabilities
- `github-app-identity`: each token asks for the permissions of the roadmap jobs, and a token that names no repository also asks for the permissions of the `metrics` row.
- `roadmap-service-alerts`: only a token that names no repository reads the hooks.

## Impact
- The token of a runner Job can no longer read a hook, a delivery or the settings of the repository. No step reads them.
- The token of the Service keeps both permissions, so the gauges of failed deliveries and of traffic do not change.
- The installation must still grant Webhooks read and Administration read, because the Service asks for them.

## Feasibility
Confirmed on 2026-11-12 against the source of `main`:
- `src/devops_cli/github/app_installation.py`, `_exchange`: each token asked for `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, which held `repository_hooks: read` and `administration: read`. A runner Job only added `repositories`.
- `git grep -n -E 'report_delivery_failures|collect_project_metrics_report' -- src`: only `src/devops_cli/roadmap/run.py` (the `metrics` row of the Service) and `devops gh metrics` on a workstation read the hooks and the traffic. A runner Job runs `roadmap implement`, which reads neither.
- `src/devops_cli/k8s/configmap.py` renders `service.github_app` with no `token_repository`, so the Service never names one repository. `src/devops_cli/roadmap/implement/implement_submit.py` and `src/devops_cli/commands/k8s/cluster_jobs.py` set `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY` on each runner Job.
- [Create an installation access token for an app](https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app): the body `permissions` limits the token to the permissions that it names, and `repositories` limits it to the repositories that it names. So the request body selects the permissions of each token.
- `tests/github/test_github_app_identity.py`: the changed tests of a runner Job token fail on `main` with `repository_hooks` and `administration` in the body and in the HTTP 422 error.

## Existing Tool Considered
The `permissions` body of GitHub's installation token API, sent through gidgethub, already selects the permissions of each token. The change adds one constant and one function. It adds no tool and builds no new mechanism.
