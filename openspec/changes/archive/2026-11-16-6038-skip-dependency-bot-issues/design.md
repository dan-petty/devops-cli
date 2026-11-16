# Design

## Decisions
- **The rule is the author login.** The issue listing gives `user.login` for each issue, and an App bot has the only login that ends in `[bot]` with its slug. A login matches only when it is equal, as in `trust.py`. The setting holds a list, so another tool bot is one more entry.
- **The rule is in one place.** `roadmap_issues` reads the setting once for each selection and drops pull requests and the issues of the bots. `select_items` and `select_candidates` start from it, and both stores use them, so `items`, `open_items`, `backlog`, `item` and `candidates` skip the issue. Intake reads `store.issues()` and filters it through the same function, so the dashboard is no candidate and no shortlist entry.
- **`store.issues()` stays every issue.** The agent audit and the Jev shadow report read it, and they are no rows.
- **The store reads the setting.** `trust.py` reads `service.github_app.bot_login` the same way. A parameter on each selection would put the rule in each caller.

## Rejected alternatives
- **A label rule.** The repository has no label that marks the tracking issue of a tool: Renovate gives the dashboard the labels of its pull requests (`type/chore`, `scope/deps`), and it removes the labels that it does not set.
- **Skip each bot other than the trusted bots.** An App that files work items, as the Service App does, would then go out of the roadmap with no setting that names it.
- **A check in each row.** Nine copies of one rule, and a new row could miss it.
- **Filter in `GitHubRoadmapStore.issues()`.** The in-memory store would need its own copy, and the audit readers of the listing would change too.
- **Turn the dashboard off in Renovate.** The approvals of a new Python minor and of a major of Node, PostgreSQL or Mattermost use it.
