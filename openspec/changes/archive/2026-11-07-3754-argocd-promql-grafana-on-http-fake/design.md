# Design

## Context

See proposal.md for the motivation and the scope (#3754, part 6 of #1335). The HTTP entry point, the `web` fixture and the `dns` fixture are #1314. The commands print and exit. The clients raise.

## Decisions

### 1. One client class for each service, open for the length of a `with` block
- **Decision**: `PrometheusClient` and `GrafanaClient` take the base URL (and the headers for Grafana) and the egress level. They build the httpx2 client through `http_client` in `__enter__` and close it in `__exit__`. A call outside the block raises `RuntimeError`.
- **Rejected**: module functions that take an open `httpx2.Client`. The command would still build the client, so the egress level and the entry point would stay in `commands/`.

### 2. The command resolves the settings, the client does the requests
- **Decision**: the URL check (`_base_url`, `_client_args`, `_argocd`) stays in the command for Prometheus and Grafana. It prints a message and exits 1, which is how a command talks to a person. Argo CD is the exception: its URL and token steps repeat in the fleet sync and the GitOps sync, so `resolve_argocd_endpoint` holds them and raises `ConfigurationError`. `_argocd` of the command catches it, prints it and exits 1.
- **Rejected**: move the Grafana token and mint steps into `grafana/client.py`. They read the keyring and mint a token. #3754 asks only for the calls to leave `commands/`.

### 3. A client returns the JSON answer, and the caller interprets it
- **Decision**: `PrometheusClient.query` returns the answer as a dict. The command parses it with `PrometheusQueryResult`, and the rollout gate takes the first sample from the same model. This removes the second copy of the instant query without a second parser.
- **Rejected**: return `PrometheusQueryResult` from the client. `analyze` needs the raw `result` list, because `extract_series_values` reads it.

### 4. A failed sync of one dashboard is a result, not an exception
- **Decision**: `GrafanaClient.sync_dashboard` returns a `DashboardSyncResult` (`SYNCED`, `SKIPPED` or `FAILED`, with the title, the file and the error text). It catches the named errors only: `OSError`, `ValueError`, `httpx2.HTTPError` and `httpx2.InvalidURL`. A refused address (`SSRFBlockedError`, a `ValueError`) is raised first, because it applies to each file and the app reports it. The blind `except Exception` of the command is gone, so its ceiling in `swallowed_failures_ceilings.json` falls to 0.
- **Rejected**: keep `except Exception` in the new module. It would move one swallowed failure and raise the ceiling of a new file.

### 5. `argocd_api_request` keeps the 401 rule
- **Decision**: `resolve_argocd_endpoint` builds the URL and the headers. The `devops argo cd apps` commands still send through `argocd_api_request`, which mints a new token after a 401. The fleet sync and the GitOps sync keep their `raise_for_status`.
- **Rejected**: send every Argo CD request through `argocd_api_request`. It would add the token refresh and a new error type to the fleet and GitOps results. That is a change of behavior, not a move.

### 6. A test of a private function tests the public function that calls it
- **Decision**: the rollout gate is tested through `evaluate_rollout_gate` with Prometheus on the `web` fake and the Rollout in the `cluster` fake. `_compare_metric` is tested through its five operators. The fleet sync is tested through `sync_single_target` and `sync_fleet`. The GitOps drift is tested through `inspect_git_manifest_drift` with the `process_fake`.
- **Rejected**: keep the private imports and swap the double. A new or changed test imports no private name (`docs/TESTING.md`).

### 7. The PromQL tests move to the package they test
- **Decision**: `tests/commands/test_promql_analysis.py` held the tests of `devops_cli.prometheus` and four command tests. The package tests move to `tests/prometheus/test_promql_analysis.py`, and the command tests move to `tests/commands/test_prometheus.py`.
- **Rejected**: leave the file in `tests/commands/`. The folders under `tests/` mirror the packages under `src/devops_cli/`.

### 8. A command test proves the wiring of the command
- **Decision**: a command test reads the requests that reached the `web` fake. The Grafana tests assert the bearer token on every request, the `query` of a search and the printed rows. The Prometheus tests assert the `time` of an instant query and the `step` and the window of `analyze`. The masked-token fallback runs as `grafana datasources` with the `keyring_store` fixture and the mint endpoints on `web`, so the test holds no patch and no private import. The drift test of `git status` replays a transcript of `git status --porcelain=v1 -z` through `process_fake`.
- **Rejected**: test the wiring through the client tests alone. A command that passes the wrong headers or drops an option would pass every client test.
