# Design

## Decisions

- **The `repo` value is `RepoRef(report.repo).key`.** ADR 0022 says telemetry uses the casefolded `owner/name`. `emit_project_metrics_telemetry` parses the report repository once and passes the one label to `_emit_traffic`, `_emit_item_counts` and `_emit_item_ages`, so each point and the state of sent label sets use the same value.
- **Every `devops_cli_project_*` instrument gets the label.** The release, CI run, star and fork series get it too, until the item of owner decision 1 moves those facts to the GitHub data source. A series with no label still has one writer for each repository.
- **The descriptions name `repo`.** `Instrument` holds no structured label set, so the description is where the dashboards and `docs/TELEMETRY.md` read the labels. `PROJECT_ITEM_LABELS` stays the four labels of `ItemCountMetric`, which holds no repository.
- **`_sent_item_series` is a dict keyed by `repo`.** One lookup gives the label sets of one repository, and `reset_sent_item_series` clears the dict.
- **The command compares `--limit` with one named default.** `DEFAULT_PROJECT_METRICS_RELEASE_LIMIT` in `config/defaults.py` is the default of the option and of `release_limit`, because modules of two packages read it. A run with `--limit 10` asks for the same series and is accepted.
- **The guard runs first.** The command refuses before `_resolve_repo` and the report collection, so a refused run makes no request and sends no point. The error is a `ValidationError` with a message of `MESSAGES.gh_metrics`, which names the option.
- **The dashboard queries stay.** The project-metrics dashboard item adds the `repo` filter. Until then the panels aggregate over the repositories.

## Rejected alternatives

- **`RepoRef.metric_value(service.repos)` as the value.** It maps a repository outside `service.repos` to `other`, so two repositories that a person runs `devops gh metrics` for share one series, and the test with `example/one` and `example/two` cannot tell them apart.
- **Build the key in each helper from `report.repo`.** Three conversions can drift: `_emit_item_ages` sent `report.repo` with no casefold.
- **Add the label in the shared `emit` helper from a process-wide value.** The metrics row runs several repositories in one process, so a process-wide value names the wrong repository.
- **Add `repo` to `PROJECT_ITEM_LABELS`.** That tuple is the labels of `ItemCountMetric.labels()`, which holds no repository.
- **Refuse every `--limit` with `--emit-telemetry`.** A person who gives the default value asks for the same series.
- **Collect the report, then refuse before the emit.** The command then spends GitHub requests on a snapshot that it refuses.
- **Filter the dashboard in this change.** The dashboard item owns the filter and the template variables, and a fixed repository in the queries now would be replaced there.
