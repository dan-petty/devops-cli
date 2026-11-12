# Proposal

## Why

The traffic row of the project dashboard has no sample since 2026-10-30. The Service acts as the GitHub App, and its installation token asks for no Administration read, so `get_repository_traffic_metrics` returns no traffic and the four panels stay empty. GitHub keeps traffic for 14 days only, so each day without a read loses data. This change delivers #4757: it gives the token the permission, removes the App skip, and names the missing permission when GitHub refuses a traffic endpoint.

## What Changes

- Add `administration` at level `read` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, so every installation token request names it.
- Remove the `acts_as_github_app()` guard and its import from `get_repository_traffic_metrics`, so a process that acts as the App reads the four traffic endpoints.
- When GitHub refuses the traffic of a repository, log one warning that names the repository and `administration: read`, in place of the debug line, and keep the refused set of repositories.
- Rename the base requirement `The Service collects no repository traffic` to `The Service collects repository traffic`, and modify it.
- Modify the base requirement `A path that the token cannot read is not asked again`: it adds the refused repository and the warning, and it corrects the count of its first scenario, as the code asks each traffic path once.
- Modify the base requirement `A refused permission names each permission that the token asks for`, because the HTTP 422 message now names eight permissions.
- Modify the base requirement `A report without traffic sends no traffic gauge`: its scenario under the App now has GitHub refuse the traffic paths.
- Record the permission in an amendment line, the decision bullet and the consequences of ADR 0015, and correct the traffic paragraph of `docs/TELEMETRY.md`.
- Update the traffic tests of `tests/github/test_github_metrics.py`, `tests/roadmap/test_roadmap_run_metrics.py` and `tests/github/test_github_app_identity.py`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-app-identity`: Each installation token asks only for the roadmap jobs' permissions
- `github-app-identity`: A refused permission names each permission that the token asks for
- `project-metrics-dashboard`: The Service collects repository traffic (renamed from The Service collects no repository traffic), A report without traffic sends no traffic gauge, A path that the token cannot read is not asked again

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/github/metrics.py`, `src/devops_cli/docs/generator.py` (the text of `docs/TELEMETRY.md`)
- Documents: `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, `docs/TELEMETRY.md`
- Tests: `tests/github/test_github_app_identity.py`, `tests/github/test_github_metrics.py`, `tests/roadmap/test_roadmap_run_metrics.py`

## Feasibility

- The probe answers the cited code path: The path `src/devops_cli/github/metrics.py` is a file of the staging commit.
- The probe answers the cited code path: The path `src/devops_cli/config/constants.py` is a file of the staging commit.
- The probe answers the cited code path: The path `src/devops_cli/github/app_installation.py` is a file of the staging commit.
- The probe answers the cited ADR path: The path `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md` is a file of the staging commit.
- The probe answers the bare dashboard name of the issue: The path `project-metrics.json` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/monitoring/dashboards/project-metrics.json`. No commit in the history deleted or renamed it. The plan edits no dashboard.
- The probe answers the setting name: The path `service.repos` is no file of the staging commit. No commit in the history deleted or renamed it. No tool of this run counts the repositories of that setting, so the count is unverified and the live check is a person's.
- `read_file` of `src/devops_cli/github/metrics.py` confirmed the premise: `src/devops_cli/github/metrics.py:763:if acts_as_github_app() or repo in _refused_integration_repos:` returns before any traffic read, and `src/devops_cli/github/metrics.py:781:logger.debug(` writes the refusal that no operator sees.
- `search_code` with `acts_as_github_app` returned one use in `src/devops_cli/github/metrics.py`: `src/devops_cli/github/metrics.py:35:from devops_cli.core.process import acts_as_github_app, run_subprocess`, so removing the guard also removes that name from the import. `src/devops_cli/core/process.py:290:def acts_as_github_app() -> bool:` stays for the other callers.
- `read_file` of `src/devops_cli/config/constants.py` confirmed the missing permission: `src/devops_cli/config/constants.py:1477:CONST_GITHUB_APP_TOKEN_PERMISSIONS: Final[dict[str, str]] = {` holds `issues`, `pull_requests`, `contents` and `workflows` at `write` and `checks`, `actions` and `metadata` at `read`, and `src/devops_cli/config/constants.py:1484:"workflows": "write",` closes the mapping with no `administration` entry.
- `read_file` of `src/devops_cli/github/metrics.py` confirmed the label of #4690: `src/devops_cli/github/metrics.py:953:repo = {"repo": RepoRef(report.repo).key}`, so the traffic gauges need no label code.
- `read_spec project-metrics-dashboard` with `A path that the token cannot read is not asked again` returned the base requirement, whose text begins `The project metrics collector SHALL NOT send a GitHub path again in the same process after GitHub answered that path with HTTP 403`, so the plan modifies that requirement and adds no second one.
- `read_file` of `tests/github/test_github_metrics.py` showed that the base scenario of that requirement is stale: `tests/github/test_github_metrics.py:1160:) == (_traffic_paths("example/repo"), [], 1)` asserts the four traffic paths once over two collections, and `tests/github/test_github_metrics.py:1138:` `The refusal logs zero warnings and one debug line (#2626).` states the refusal that the change rewrites.
- The corrected requirement text now holds about 450 characters, under the 500 that the check allows, and the refused-set rule and its warning sit in its first scenario.
- `read_spec github-app-identity` with `Each installation token asks only for the roadmap jobs' permissions` returned the seven-permission text, so the modified requirement keeps its one scenario and names the eighth permission.
- `read_file` of `tests/github/test_github_app_identity.py` showed `tests/github/test_github_app_identity.py:43:ROADMAP_PERMISSIONS = {`, the constant that the identity test compares with the request body.
- `read_file` of `tests/roadmap/test_roadmap_run_metrics.py` returned `tests/roadmap/test_roadmap_run_metrics.py:170:def test_the_metrics_job_of_the_app_asks_no_traffic_endpoint(`, which asserts that the App sends no traffic request and must now assert the four requests.
- `read_file` of `tests/github/test_github_metrics.py` returned `tests/github/test_github_metrics.py:1072:def test_the_app_asks_no_traffic_endpoint_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:` and `tests/github/test_github_metrics.py:1224:def test_the_command_prints_that_the_app_collected_no_traffic(`, the two App tests that the group rewrites.
- The failure class of a `docs` check is `lint` and not `test`: `src/devops_cli/roadmap/failure.py:317:` `r"lint|ruff|format|static|bandit|security|pre-push|pre-commit|actionlint|openspec|docs",`, while `src/devops_cli/roadmap/failure.py:314:_rule(FailureClass.TEST, r"test|coverage|pytest"),` gives `test` only for a log that names a test.
- The ADR group has no command, because `uv run devops ci docs` reads no ADR text: `src/devops_cli/commands/ci.py:2140:` `"""Verify (or update with --fix) that documentation is up to date with CLI commands and configuration."""`. That command would pass with or without the amendment line, so the group gives a manual check instead.
- GitHub's table of the permissions of a GitHub App (docs.github.com, "Permissions required for GitHub Apps", section "Repository permissions for Administration") lists `GET /repos/{owner}/{repo}/traffic/views`, `traffic/clones`, `traffic/popular/paths` and `traffic/popular/referrers` at the level `read`, for the token types `UAT` and `IAT`. So an installation access token that holds `administration: read` can read the four endpoints.
- ADR 0015 records that the owner gave the App read and write on every repository permission (#2454), so the installation grants `administration`, and a token request that names it at `read` gets no HTTP 422.
- The live premise is not checked by this change: a probe that mints an installation token with `administration: read` in the Service pod and reads `traffic/views` was refused by the permission check of the agent session. A person runs the probe before the merge. It must print HTTP 200 for the four traffic paths. An HTTP 422 at the mint means that the installation does not grant `administration`, and the change must not merge, because each token of each job would then fail.
- `get_repository_traffic_metrics(repo)` needs a client of GitHub through `GhCliClient` and a network for each of its reads.
- `_fetch_repo_metadata(client, repo)` needs a client of GitHub and a network, and the plan reaches it through `get_repository_traffic_metrics`.
- `mint_installation_token()` needs the App's settings and a network to `POST /app/installations/<id>/access_tokens`.
- `emit_project_metrics_telemetry(report)` needs a client of the OTLP collector and a network to it.
- The verifies introduce no program of their own: `uv run devops ci test` runs `pytest`, which the runner image holds, and a failure is the class `test` with the action `repair`. Both groups run in the pod with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`, and the tests write only under `tmp_path`.
- The change adds no command and no verify program of its own, so it needs no failure class beyond `test` and no tool outside the runner image.

## Existing Tool Considered

Grafana Infinity and prometheus-community/json_exporter read the traffic endpoints but cannot mint a GitHub App installation token, so each needs a long-lived token with Administration read, and the Grafana GitHub data source has no traffic query. The owner kept the devops-cli emitter on 2026-11-11, so the change builds on it: about 40,000 tokens and 1 hour to build, about 1,000 tokens a month to keep, and about 2,000 tokens to repair a wrong permission name. The change deletes the `acts_as_github_app()` guard and its import in `get_repository_traffic_metrics`, and the debug line that hid the refusal.

## Dependencies

- Pull request #4990 and pull request #4978 change `src/devops_cli/config/constants.py` in other lines; this change adds one entry to `CONST_GITHUB_APP_TOKEN_PERMISSIONS`.
- Pull request #4986 changes `openspec/specs/project-metrics-dashboard/spec.md` in another requirement.
- The metric `devops_cli_project_traffic_views` is also held by `k8s/monitoring/dashboards/project-metrics.json`, `openspec/specs/project-metrics-dashboard/spec.md` and `src/devops_cli/telemetry/instruments.py`; the change reads them as they are, and it corrects the traffic paragraph of `docs/TELEMETRY.md`.
