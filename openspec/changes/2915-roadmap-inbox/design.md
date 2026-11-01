# Design

## Decisions

- **One function reads the inbox, the command prints it.** `read_inbox(store, repo, now)` returns an `Inbox`: the lines of the jobs, in the order of the gates, and the lines of people and agents. The command renders it. W10 (#2919) can count the same lines for its metrics, so the counts and the list cannot differ.
- **The store reads, the inbox judges.** `open_items`, `open_pulls` and `repository_labels` are plain reads on `RoadmapStore`, kept by both adapters. The rules (which pull request is a job's, what an old claim is) live in `inbox.py` only. A test with the in-memory store shows every category.
- **Open issues, not every issue.** `open_items` reads `issues?state=open`. The store keeps the listing of every issue for its life, and that is about 30 pages. The inbox needs only open items: blocked items and claims on open issues, and the records of open items for the pull request numbers. A closed item holds no `status/*` and no `owner/*` label, because `clear-status.yml` removes them.
- **A job pull request is named by a record.** `implement.pr` wins over `stage.pr`, because a staged branch keeps one pull request through both jobs. The record is exact; the title or the branch name is not. A pull request of an item that a Job holds (`implement.job` and no `implement.job_state`) is not listed: the Job pushes to it.
- **A draft is not "waiting".** The jobs' sections list only pull requests that are not drafts. The people section lists every pull request that no record names, a draft too, with the step that moves it on. This answers the case of 2026-10-31: a person sees at once which pull request is finished.
- **The age is the time since the last update.** For a pull request or an issue it is `updated_at`. GitHub gives no "ready since" time without one more request for each pull request. The heading says what the age means.
- **The activity of a claim.** It is the newest `updated_at` of the issue and of each open pull request whose head branch names the issue. The claim label write itself moves the issue, so a new claim is never old. A claim is old after `CONST_ROADMAP_INBOX_CLAIM_DAYS` days. The clearing step is `devops roadmap release <n> --confirm`. No job releases a claim, and the inbox only shows it.
- **The cause of a block.** It is `implement.stopped` (the step that stopped the item), else `refine.blocked_by`, else the text "no cause recorded". The step for a stopped item is the retry comment; the step for the others is to read the issue and to set the status by hand.
- **Labels.** The declared labels come from `.github/labels.yml` on the default branch, parsed by the spec type that `devops gh labels sync` uses. `diff_labels` names the labels to create or update. One line lists them. The age is the time since the file last changed on the default branch, which is a lower bound on how long the repository is behind.
- **The digest is left out.** See the proposal. The help text of the command says so.
- **The dry run lists the reads.** `inbox_requests` is built by `StoreRequests`, the same builders the store runs, so the plan cannot drift. The labels read of the second file is a condition.
- **No cap on lines.** The list is as long as the work that waits. A cap would hide work.

## Rejected alternatives

- **Read every issue with `items()`.** About 30 requests for each run, against 2. The Service budget is 500 requests an hour. Rejected on cost.
- **Find a job pull request by its title or branch.** A job and a person use the same forms. A record is exact and already exists. Rejected: a guess would put a person's pull request in the jobs' list.
- **Ask GraphQL for pull requests with their ready time and checks.** One query would give more, but the project keeps GraphQL for the places that need it, and the quota can run out while REST has room. REST with 3 reads is enough.
- **A commit read for each claim.** One more request for each claim and a branch listing. The pull request update time covers the case, since the workflow opens a draft with the first push. Left as a later step if the list shows a false claim.
- **Read the cluster for the digest.** A cluster call from a command that the Service may run, with no GitHub request budget. Rejected: `devops argo cd apps status` is the tool.
- **A Grafana panel now.** It needs metrics, and the metrics are W10. A panel on a second data path would be rebuilt.
- **An open tool.** No open tool knows the records of the jobs.
