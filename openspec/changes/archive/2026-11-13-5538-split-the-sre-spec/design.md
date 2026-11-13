# Design

## Decisions

- **A guideline, decisions and generated facts.** The guideline holds what applies with no change to each managed project. The README of the environment tree holds the decisions of one cluster. A dashboard, a command or the project review report gives each measured value, and no document copies it.
- **Two guidelines.** The SRE guideline holds the method. The production readiness guideline holds the 91 rows, because an agent reads them only for a launch or a review.
- **A check for each row.** The Evidence column of the draft becomes "Measured by": the Scorecard check, the kube-linter check, the command, the query or the file that reads the row. A row that no program reads says `manual`. The readiness report of the launch branch is the record of a launch, so no agent copies 90 row states into a document.
- **Catalog data, not a prose table.** `k8s/catalog.toml` holds only the decisions that no other file holds: the Applications, the tier, the data class and the dependencies. A Sloth spec names its service and `services.toml` names its dashboard workload, so the file holds no SLO id and no dashboard uid. A service with a Homepage UI takes its description from the annotation of #4600 (owner decision 5).
- **One entry for each service.** The rows of Table 2 that named several products become one entry for each product: Crawl4AI and SearXNG, Gitea and Mattermost, and each part of the observability stack. A workload list takes a glob pattern, so a new Ollama tier needs no edit.
- **Catalog values of the data classes.** The data class table of the guideline gives the value of each class in the catalog data: `external`, `derived`, `owned`, `telemetry` and `none`.
- **Events start the automation.** The owner asked that jobs run asynchronously and be ready for event-driven triggers. The SRE guideline holds the SRE part: an Alertmanager webhook receiver starts the incident job, a scheduled pass reads the triggers again, and the SLO or the alert is the key of the record. The agentic jobs guideline and the Kubernetes guideline own the rules of the job itself.
- **Gaps in a tracker.** Tracker #5541 holds the gaps of SRE.md Table 8 and of the draft Table 10. "Service levels" links it and holds no gap row, so an issue that closes changes no document.
- **The same shared files as PR #5492.** The guideline test, the Guidelines tab and the `docs/TESTING.md` line are byte for byte the files of PR #5492. The index page has the lines of this change. The second pull request to merge rebases and keeps each index line.

## Rejected alternatives

- **Keep the current state and the queries with a date.** The owner directions replace them: a measured row in git goes stale, and an agent must update it by hand.
- **A service table in prose.** #5535 renders the catalog page from the data and the manifests. A prose table is a second copy that drifts.
- **A description for each service in the catalog data.** Owner decision 5 keeps one description for each service, and the Homepage annotation holds it for a service with a UI.
- **A gap table in the README.** The owner chose tracker issues.
- **The admission policy comment fix of the draft.** It is a manifest change, so it goes in its own pull request.
- **A spec delta.** `openspec/config.yaml` gives a documentation change no delta.
