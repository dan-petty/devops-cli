# Design

## Decisions

- **The Service learns it is the App from `acts_as_github_app()`.** It is the test behind `github_identity()`: the process acts as the App when its environment holds the App's private key, and then the token is an installation token that ADR 0015 narrows. The collector asks the predicate and not `GITHUB_ACTIONS`, a host name or a pod variable, so there is no environment guess beyond the one that defines the identity. Tests set the predicate in `devops_cli.github.metrics`, as the implement tests already do for their module.
- **The report says what it did not collect.** `TrafficSummaryMetric.traffic_collected` is true by default and false when the process is the App. A false value makes `emit_project_metrics_telemetry` skip the six traffic series, so Prometheus gets no new sample and a panel shows no data once the range passes. `--json` shows the field, and the table of `devops gh metrics` prints "not collected".
- **Stars and forks stay.** `GET /repos/{repo}` needs only Metadata (read), which the token holds.
- **The guard is keyed by the path.** The path `repos/<repo>/traffic/views` holds the repository and the endpoint, so one string is the key. The set lives in `github/metrics.py` with a `reset_refused_paths` function, which `tests/conftest.py` calls between tests as it does for `reset_sent_item_series`.
- **The guard keys on gh's words.** `gh api` writes `gh: Resource not accessible by integration (HTTP 403)` to stderr, and `GhCliClient.api` keeps the first 256 characters of stderr in the error details. `is_gh_refused_by_token` in `error_classifier.py` tests the status with the existing `gh_http_status` and the phrase with the existing `_gh_says`, next to the other gh-output tests. A 403 for a rate limit, a suspended installation or a missing scope has other words, so it does not set the guard.
- **One helper for four reads.** `_fetch_traffic_views`, `_fetch_traffic_clones`, `_fetch_traffic_referrers` and `_fetch_traffic_paths` each repeated `try: json.loads(client.api(...)) except Exception: log`. They now call `_read_json(client, path, what)`, which owns the guard, the call, the parse and the one warning. The repository read uses it too, so the next refused path is not asked again either.
- **The warning comes once.** The first refusal logs the existing warning. Later rounds skip the call and log nothing.

## Rejected alternatives

- **Give the metrics row its own token with Administration (read).** The issue and ADR 0015 leave this to the owner: it adds a permission to the App. This change must not change the App permissions or the token permissions.
- **Add `administration: read` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS`.** Same reason. GitHub also refuses a token with HTTP 422 when the installation lacks a listed permission, so the change would break every token if the owner has not granted it.
- **Catch the 403 and stop only through the guard.** Each Service start would still spend one request per endpoint and repository, and each restart would log the warnings again, for calls that the token can never win. The skip by identity costs nothing and says why.
- **Decide by `get_github_session().identity.renews`.** It is the same fact, but for a workstation it runs `gh auth token` and can raise `GitHubUnauthenticatedError` for a question about a feature flag. The predicate needs no subprocess.
- **Send 0 for the six series under the App.** A 0 reads as "no visitors" in a stat panel. Before this change the failed read already sent 0. The spec for the gauge panels says a panel with no value shows no data, so the Service sends nothing.
- **Guard inside `GhCliClient.api` for every caller.** It would change the behavior of all GitHub reads in all commands, for a fault in one collector. The collector owns the helper, and a later collector can use it.
