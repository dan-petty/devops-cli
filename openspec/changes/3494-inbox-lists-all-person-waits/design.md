# Design

## Context

`read_inbox` in `src/devops_cli/roadmap/inbox.py` reads one repository and returns the lines of the jobs and the people. Its line builders are pure functions over the open items and the open pull requests of a store. The store protocol is `RoadmapStore` in `src/devops_cli/roadmap/store.py`. The command `inbox_cmd` in `src/devops_cli/commands/roadmap.py` opens one store from `--repo` or from the origin of the checkout.

## Decisions

### One read per repository in `service.repos`

`inbox_cmd` loops over the repositories of `service.repos` when `--repo` is not given, and calls `read_inbox` for each one. `read_inbox` keeps its shape, so each repository has its own reads, its own counts and its own sections.

Rejected: reading the origin of the checkout when `service.repos` is empty. The checkout hides the repositories that the Service runs. The project rule for unconfigured service URLs says to fail and name the setting. The command therefore raises `ConfigurationError` that names `service.repos`.

### Three new classes, in the order of the issue

`InboxKind` gets `SPLIT`, `ALTERNATIVES` and `DRAFT`, after `REFINE`. The person wait and the returned item stay in `REFINE`, because the rule of `refine_wait_on_person` already covers them. The rule for a returned item is kept, since no new record key replaces it.

- `SPLIT`: an open New item whose `refine.next_step` is `split`. The item stays open until a person splits it. A reply shows after the next refine round, as it does for `REFINE`.
- `ALTERNATIVES`: an open New item whose `refine.alternatives_asked` is set. The key is set when the check verdict is `covers` (`refine.py:2079`). The key is read, not the next step, because the covers question joins the open questions only after a reply (`refine.py:560-564`).
- `DRAFT`: a draft of a job, which is a draft pull request that a job record names and that no runner Job holds. It is listed when its age is over `roadmap.inbox.draft_days` or when a check run of its head commit failed.

An item may have more than one line, one for each wait. A `REFINE` line and an `ALTERNATIVES` line of one item both show.

### Check runs by head commit

`OpenPull` gets `head_sha`, read from `head.sha` of the pull request listing. `RoadmapStore.failed_checks(head_sha)` returns whether a check run of the commit failed. The GitHub store calls `read_check_runs` and returns `fail_count > 0`. When GitHub gives no check run list (`unread_reason` is set), the store raises `GitHubUnreadError`, so the inbox does not show a draft as passing. The in-memory store answers from the failures that a test seeds.

The inbox reads the check runs only for job drafts, so a run makes one read for each job draft and no read for a person's draft.

Rejected: reading the check runs of every open pull request. It costs one request for each person's draft, and the rule needs only the job drafts.

### Two settings with a default of seven days

`roadmap.inbox.draft_days` and `roadmap.inbox.wait_days` are integers of at least 1. Both default to 7 (`DEFAULT_ROADMAP_INBOX_DRAFT_DAYS` and `DEFAULT_ROADMAP_INBOX_WAIT_DAYS` in `config/defaults.py`). `CONST_ROADMAP_INBOX_CLAIM_DAYS` stays a constant, because the spec rule of claims names its 7 days.

Rejected: one setting for both thresholds. The issue names a setting for drafts and a setting for the mark, and the two thresholds can differ.

### Marks, counts and the class filter

`InboxLine` gets a field `old`, which `read_inbox` sets when the age of the line is over `wait_days`. `render_inbox` prints the mark after the subject of an old line.

`render_inbox` prints the counts of all lines by class under the title, before any filter. `render_inbox` takes an optional set of classes, and the command option `--kind` passes one class. The counts stay complete when a filter applies.

Rejected: the option name `--class`. `class` is a Python keyword and the code names the type `InboxKind`, so the option is `--kind`.

### Dry run

`inbox_requests(repo)` lists the reads of one repository. It adds the check-run read of each open job draft, under the condition `open job draft`, so a dry run lists the reads that a run may make and makes none.

## Rejected alternatives with their evidence

- Reading the origin of the checkout when `service.repos` is empty: rejected for the reason above (the project rule on unconfigured service URLs).
- A record key for the returned item: rejected, because the rule `RETURNED_BODY_HASH == BODY_HASH` already gives the line, and the issue allows keeping the rule.
- Reading the check runs of every pull request: rejected because it costs a request for each person's draft.
