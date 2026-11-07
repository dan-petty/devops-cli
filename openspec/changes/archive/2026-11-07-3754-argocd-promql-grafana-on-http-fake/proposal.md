# Proposal

## Why

Issue #3754 is part 6 of 6 of #1335. Argo CD, Prometheus and Grafana code sends its HTTP requests from `commands/`, behind private helpers, and the tests of that code patch names instead of using the HTTP fake.

- `commands/prometheus.py` builds a client (`_client`) and calls the Prometheus API in five commands. `argo/rollouts.py` holds a second copy of the instant query.
- `commands/grafana.py` sends all its Grafana calls itself. The rule that a refused save of a provisioned dashboard is a skip sits in three private helpers (`_is_provisioned`, `_post_dashboard`, `_sync_dashboard_file`).
- `commands/argo.py` resolves the Argo CD URL and token (`_argocd`, `_argocd_client`) and builds a public client for the image pins (`_check_image_pins`). `argo/fleet.py` and `argo/gitops.py` repeat the token and header steps.
- `tests/argo/test_argo_fleet.py`, `tests/argo/test_argo_gitops.py` and `tests/commands/test_promql_analysis.py` hold 41 patch sites, 2 private imports and 3 module-level `CliRunner()` objects at the start of this change. The patches replace `httpx2.Client`, `load_settings`, `_execute_cluster_sync`, `ArgoCRDService._api`, `abort_rollout`, `sync_fleet`, `run_subprocess`, `_run_mcp_cmd` and the metrics registry. The HTTP entry point and the `web` and `dns` fixtures (#1314) now make every one of these unnecessary.

## What Changes

- New public clients, one for each service, built on the HTTP entry point (`devops_cli.http.entry.http_client`):
  - `prometheus/client.py`: `PrometheusClient` (`query`, `query_range`, `rules`, `targets`), `expression_problem` and `parse_duration`. The commands use it. `argo/rollouts.py` reads the metric with `PrometheusClient.query`, so the second copy of the instant query is gone.
  - `grafana/client.py`: `GrafanaClient` (`list_dashboards`, `search`, `dashboard`, `import_dashboard`, `datasources`, `alert_rules`, `is_provisioned`, `sync_dashboard`) and `DashboardSyncResult`. The command prints and counts.
  - `argo/client.py`: `resolve_argocd_endpoint` and `ArgoCDEndpoint`. It reads the URL and the token once and builds the headers. The `devops argo cd apps` commands, `argo/fleet.py` and `argo/gitops.py` use it. `argo/image_pins.py` gets `check_application_pins`, which replaces `_check_image_pins` of the command.
- The commands keep their options, their messages and their exit codes. They resolve settings, call the client, and print.
- Tests:
  - New tests of each client run on the `web` fixture: `tests/prometheus/test_prometheus_client.py`, `tests/grafana/test_grafana_client.py`, `tests/argo/test_argo_client.py` and two tests in `tests/argo/test_image_pins.py`.
  - `tests/argo/test_argo_fleet.py`, `tests/argo/test_argo_gitops.py` and the CLI part of `tests/commands/test_promql_analysis.py` use the `web`, `cluster`, `process_fake`, `mcp_dispatcher`, `config`, `keyring_store` and `cli` fixtures. They hold no patch site, no private import and no module-level `CliRunner()`.
  - `tests/commands/test_promql_analysis.py` tests `devops_cli.prometheus`, so it moves to `tests/prometheus/test_promql_analysis.py`. Its four command tests move to `tests/commands/test_prometheus.py`.
  - `tests/commands/test_prometheus.py` and `tests/commands/test_grafana.py` keep wiring only. The cases of the moved rules move to the client tests.
- Ratchet: `commands/grafana.py` holds no blind `except` any more, so its ceiling in `tests/fixtures/swallowed_failures_ceilings.json` falls from 1 to 0. The client catches the named errors only.
- Documents: `ARCHITECTURE.md` names the three clients, and the knowledge base pages of Grafana and Prometheus link them.
- This change alters no behavior in the spec of a command. The commands keep their options, messages and exit codes. Two failure texts of the Argo CD sync change: a missing `argocd.url` in the fleet sync now gives the message of the commands (it names the setting), and a `k8s://` address in `argocd.url` now stops the fleet sync and the GitOps sync with the error that names the setting, where httpx2 raised before. No spec in `openspec/specs/` holds either text, so the change has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- `src/devops_cli/prometheus/client.py`, `src/devops_cli/grafana/client.py` and `src/devops_cli/argo/client.py` (new); `src/devops_cli/argo/` (`fleet.py`, `gitops.py`, `rollouts.py`, `image_pins.py`); `src/devops_cli/commands/` (`prometheus.py`, `grafana.py`, `argo.py`).
- `tests/prometheus/`, `tests/grafana/`, `tests/argo/`, `tests/commands/test_prometheus.py`, `tests/commands/test_grafana.py`, `tests/fixtures/swallowed_failures_ceilings.json`.
- `ARCHITECTURE.md` and the Grafana and Prometheus pages of the knowledge base.

## Feasibility

Checked on `origin/main` 6d105c20, 2026-11-07. The premise of #3754 holds in part. The tree has moved since the issue was written, so each claim was read again.

- The block is gone. #1314 is done: `git grep -n "def http_client" -- src/devops_cli/http/entry.py` finds the entry point, and `tests/support/fakes/http.py` holds the `web` fixture. `new_http_client` has no caller in the three command files, in `argo/` or in `prometheus/`: `git grep -n "new_http_client" -- src/devops_cli/argo src/devops_cli/commands/argo.py src/devops_cli/commands/grafana.py src/devops_cli/commands/prometheus.py` prints nothing. The slice #3789 (archived) moved `argo/fleet.py`, `argo/gitops.py`, `argo/rollouts.py` and `commands/argo.py` to `http_client`, and #3758 moved `commands/grafana.py` and `commands/prometheus.py`.
- The measured counts of the issue are out of date. At the start of this change the three files held 31, 5 and 5 patch sites (41 in all, not 61), and 2 private imports (not 5). #3789 had moved the sync and metric tests of the fleet to the `web` fixture, and `test_fetch_metric_value_branches` is already gone.
- The clients that the issue rejected are still the wrong tool. The issue read their wheel sources on 2026-11-06: `prometheus-api-client` and `grafana-client` open their own `requests` and `niquests` sessions, so the egress check of `vet_addresses` and the `web` fixture do not reach them, and the Argo CD packages on PyPI are unmaintained.
- The issue lists `labels` and `alerts` as Prometheus calls. The commands send neither. They send `query`, `query_range`, `rules` and `targets`, so the client has those four.
- The Grafana commands send six calls besides the sync (list, search, export, import, datasources, alerts). The issue names the sync helpers only. All the calls move, so that no command builds a request.
- `_execute_cluster_sync`, `_fetch_metric_value` and `_compare_metric` stay private. Their tests call `sync_single_target` and `evaluate_rollout_gate`. The `Unsupported rollout metric operator` branch of `_compare_metric` cannot be reached through the public function, because `RolloutMetricThreshold` accepts only the five operators. This change does not touch that branch.
- `git grep -n "mcp_dispatcher" -- tests/support/fakes/mcp_dispatcher.py` shows the dispatcher fake. The four MCP tests in `test_argo_fleet.py` patched `_run_mcp_cmd`. They use the fixture now. They stay in `tests/argo/` because the MCP test files belong to #1330.

## Existing Tool Considered

- `prometheus-api-client` (depends on `requests`), `grafana-client` (depends on `niquests`) and the Argo CD packages on PyPI (`argocd-python-client`, `argocd`) were checked in #3754. The first two dial through their own sessions, which skips the egress check of `vet_addresses` and the HTTP fake. The Argo CD packages are unmaintained. The project rule allows only reputable, maintained dependencies. Rejected.
- `httpx2` (open, maintained) is the HTTP library of the project, and `devops_cli.http.entry.http_client` is its entry point. The three clients are thin wrappers over it. They add the paths of the three APIs, the `raise_for_status` rule, and the checks that the commands already had. The change builds them. The cost is about 120,000 tokens to build, about 5,000 tokens each month to keep, and one day of elapsed time. It deletes `_client` and `_read_json` and the bodies of `_parse_duration` and `_validate_expr` in `commands/prometheus.py`, the five Grafana helpers of `commands/grafana.py`, `_argocd_client` and `_check_image_pins` of `commands/argo.py`, the token steps of `argo/fleet.py` and `argo/gitops.py`, and the copy of the instant query in `argo/rollouts.py`.
