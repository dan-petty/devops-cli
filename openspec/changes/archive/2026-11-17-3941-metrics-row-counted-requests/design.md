# Design

## Decisions

- **Pass one session to workflow and milestone readers.** `collect_project_metrics_report` accepts an optional `session: GitHubSession | None = None`. It passes that session to `get_ci_workflow_metrics` and `get_milestone_metrics` so both calls share the same ETag cache and quota ledger. When no session is provided, `get_github_session()` provides one.
- **Derive taxonomy from open Items in the store.** `get_label_taxonomy_metrics` takes `store: RoadmapStore`. It iterates over open Items (`item.state is GitHubState.OPEN`) in `store.items()`, extracting labels containing `/`. It makes no network call to `repos/<repo>/issues?state=open`.
- **Lower the request budget to 4.** The metrics row round previously budgeted 5 requests: every-issue listing, CI runs, milestones, open issues, and repository metadata. Removing the open-issue listing reduces the baseline budget to 4 requests.

## Rejected alternatives

- **Create a separate session in each reader.** Rejected: creating separate sessions fragments the ETag response cache and could cause duplicate fetches.
- **Keep the open-issue listing alongside store counts.** Rejected: the store already holds all open items, and duplicate listings waste GitHub API quota.
- **Add a second taxonomy cache.** Rejected: caching outside the roadmap store duplicates data and introduces a second source of truth.
