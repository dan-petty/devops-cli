### What happened

GitHub suspended the roadmap Service's machine account on 2026-10-10 at 22:49:56 UTC for suspicious activity (the owner, 2026-10-24; #1562 holds the Service at 0 replicas since). Loki (`{namespace="devops", container="service"}`) shows what the account did, read on 2026-10-24:

- **Volume.** The paced GitHub wrapper logged `[RateLimit] Mandatory pause` for each request: 800 to 1,700 requests per hour, every hour, for at least the two days before the suspension (2026-10-09 00:00 to 2026-10-10 22:00 UTC), about 15 to 28 requests a minute from one user account, across 8 repositories (devops-cli, homelab, danielpetty.com, dotfiles, dreamscaper, vibes, github-actions, devcontainer-features).
- **Rounds.** `devops_cli.roadmap.run` started a round for each repository about every 5 minutes. A refine round read all issues of devops-cli page by page (`Could not read issues (page 14)` was the call that got the first 403).
- **Failing jobs repeated.** `Roadmap jobs failed: intake` for dan-petty/devops-cli at 15:34, 15:41, 16:37 UTC and later: the job ran again at each round.
- **No stop after the suspension.** From 22:49:56 every call got `gh: Sorry. Your account was suspended (HTTP 403)`, and the Service went on at about 1,100 requests in the next hour, and logged until the next morning, when the Deployment went to 0 replicas.

#1647 changes the identity to a GitHub App installation, and #1533 makes webhooks drive scoped updates. Neither one sets a request budget, and neither one stops the Service when GitHub refuses its identity.

### What should happen

- On a reply that says the identity is suspended, revoked or unauthorized (HTTP 401, or 403 with `account was suspended`), the Service stops every job for every repository at once, reports one error, raises an alert, and makes no other GitHub request until a person restarts it.
- The Service keeps its GitHub requests under a budget for each hour that a person sets, with the poll cadence and listing reads derived from it (conditional requests with `ETag`/`If-None-Match` for listings, so an unchanged listing costs no primary rate limit), and it stops a job that fails at each round after a set number of failures until its input changes.

### Evidence

- The Loki queries above (2026-10-09 to 2026-10-11).
- `src/devops_cli/roadmap/run.py` (`_execute_due_rows`, `service_job`) and `src/devops_cli/server/service.py` (`_execute_batch`): each failure is logged and the next round runs.

### Acceptance criteria

- [ ] A test gives the Service a GitHub fake that answers 403 `account was suspended`, and shows that no other request goes out for any repository after it, and that one alert metric or log line names the identity.
- [ ] A test shows that a round stays under the configured hourly budget, and that an unchanged listing is read with a conditional request.
- [ ] A test shows that a job that failed N rounds in a row does not run again until its input changes.


Source: https://github.com/dan-petty/devops-cli/issues/1647

regression of #1562
