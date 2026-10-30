# Proposal

## Why

Issue #2752. The `metrics` row of the roadmap Service asks four GitHub traffic endpoints for each repository in every round: views, clones, popular referrers and popular paths. All four answer HTTP 403 "Resource not accessible by integration". Each failed call spends part of the hourly budget `service.github_requests_per_hour` (500). The calls are about 110 of the 420 requests of an hour, one fifth of the budget. The model-lane rows wait for that room.

The 403 follows from #2473. Each installation token of the App asks only for `CONST_GITHUB_APP_TOKEN_PERMISSIONS`: issues, pull requests and contents (write), and checks, actions and metadata (read). The traffic endpoints need the repository permission Administration (read), so the row asks for more than its token holds.

## What Changes

- A process that acts as the GitHub App (`acts_as_github_app()`, the test that `github_identity()` uses to pick the App) sends no request to the four traffic endpoints. The report of `get_repository_traffic_metrics` sets the new field `traffic_collected` to false, and `emit_project_metrics_telemetry` sends none of the six traffic series for it. The Service sends the stars and the forks as before. The dashboard panels for traffic already read `last_over_time` with no `or vector(0)`, so they show no data for the Service.
- A process with a person's login (`devops gh metrics` on a workstation) keeps the four calls and the six series.
- The metrics collector remembers each GitHub path that answered HTTP 403 "Resource not accessible by integration" and does not send that path again in the same process. The key is the whole path, so it holds the repository and the endpoint. A restart clears it. The guard covers the traffic paths and the repository read, and any path that the collector reads through the same helper later.
- `devops gh metrics` prints "not collected" for the traffic line when the report has `traffic_collected` false.
- The permissions of the App and of the token do not change. Giving the row a token with Administration (read) is the owner's decision, as ADR 0015 says, and this change does not make it.
- The change alters what the Service sends and what a command prints, so it carries one spec delta: added requirements in `project-metrics-dashboard`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: two added requirements, `The Service collects no repository traffic` and `A path that the token cannot read is not asked again`. No existing requirement changes. The gauge names in "Only a counter name ends in `_total`" stay the same, because a workstation still sends all of them.

## Impact

- `src/devops_cli/github/metrics.py`, `src/devops_cli/github/error_classifier.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`.
- `tests/test_github_metrics.py`, `tests/test_github_errors.py`, `tests/test_roadmap_run.py`, `tests/roadmap_github_fake.py`, `tests/conftest.py`.
- The expected effect on the budget: `increase(devops_cli_github_requests_total{row="metrics"}[1h])` falls by about 110 for the seven repositories.

## Feasibility

- The fault is real. On 2026-10-30, a read of the Service log in Loki (`{namespace="devops", service_name="roadmap-service"}`) for the last hour counted 22 warnings "Resource not accessible by integration (HTTP 403)" for each of the four kinds: `traffic views`, `traffic clones`, `traffic referrers` and `popular paths`. Each line is `gh: Resource not accessible by integration (HTTP 403)` from `devops_cli.github.metrics`.
- The permission is named by GitHub. The page "Permissions required for GitHub Apps" (docs.github.com/en/rest/overview/permissions-required-for-github-apps) lists `GET /repos/{owner}/{repo}/traffic/views`, `/clones`, `/popular/paths` and `/popular/referrers` under "Repository permissions for Administration" with access `read`. The OpenAPI description of GitHub (`github/rest-api-description`, `api.github.com.json`) marks the four operations `enabledForGitHubApps: true`, so an App can call them with that permission. `administration` is not in `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, so the token cannot.
- The session type exists. `acts_as_github_app()` in `core/process.py` is the one test of "this process is the App". `github_identity()` branches on it, and it returns an identity with `renews=True` and the bot login. It reads the environment for the App's private key, which Secret `devops/devops-cli` gives to the Service. `get_github_session().identity` would give the same answer, but for a workstation it runs `gh auth token`, a subprocess, to answer a question that the predicate answers without one. Other code and tests already use the predicate (`roadmap/implement_run.py`).
- The dashboard needs no change. The six traffic panels read `max(last_over_time(...[$__range]))` or `topk(10, sum by (...) (last_over_time(...)))` with no `or vector(0)`, and their descriptions say "no data when none was sent in it". No alert rule or recording rule reads a `devops_cli_project_traffic_*` series (a search of `k8s/` and `src/` finds only the dashboard `k8s/monitoring/dashboards/project-metrics.json`).
- On the base, the new tests fail: a collection under the App sends four traffic requests, and a second collection after a 403 sends them again.

## Existing Tool Considered

The GitHub REST documentation and the installation token permissions of ADR 0015 cover the facts. No library skips a refused request: gidgethub and gh send what they are given. The skip is one `if` on an existing predicate. The guard is a set of paths and one test of gh's message, with `gh_http_status`, which exists, reading the status. The code is about 25 lines and replaces four copies of the same `try` block in `metrics.py`, which the change deletes.
