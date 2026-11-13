---
status: accepted
date: 2026-11-11
decision-makers: [owner]
issue: 4527
tracker: 4517
supersedes: ["0003"]
amends: ["0008", "0009", "0017"]
amended-by: ["0023"]
body-hash: 3ee9ca4d8be1fb10a4ba43f6c48700a43bac3fbff50512e98c783f8cf7e17231
---

# The roadmap Service is a webhook router, cluster pods run the roadmap jobs, and Valkey holds their shared state

The roadmap Service runs every roadmap job in one pod. About 19 releases and ConfigMap edits a day restart that pod. Each restart stops the rounds that run in it, and a stage round runs for 21 minutes at the median. This record moves each job out of the Service pod into a pod of its own on Argo Workflows, and it moves the state that the jobs share into Valkey. The Service keeps only the webhook router.

## Context

Facts measured from 2026-11-04 to 2026-11-11:

- **Restarts stop work.** The Service shut down 133 times in 7 days. Since 2026-11-07, 53 of 71 restarts stopped a running stage round, and stage opens about 11 draft pull requests a week. The drain stops after 120 seconds. A stage round runs 1,244 seconds at p50 and 6,547 seconds at p99 on `dan-petty/devops-cli`. A stopped row runs again from its start, because the row writes its last success after it returns.
- **The token loss is not measured.** About 146M tokens a week fall in the 10 minutes before a shutdown. That is 9.6 percent of the 1,515M tokens a week of the Service in about 13 percent of the time, so it is the base rate. The Service does not count a model call that a restart stops.
- **Restarts drop webhooks.** The Deployment uses `Recreate`, because its volume is ReadWriteOnce. No replica receives webhooks for about 37 minutes a day, about 116 seconds for each rollout. GitHub does not redeliver a failed delivery by itself.
- **The state is bound to one pod and one node.** The self-cap of the request budget, the schedules, the intake record, the ledgers and the stage plan records are files on a ReadWriteOnce volume. The lane queues, the delivery cache, the GraphQL pause and the job record lock are in process memory. Each process sees the real GitHub quota in the rate-limit headers, but only the Service counts against the self-cap.
- **The job record lock does not cover all writers.** The runner Job and the claims write job records outside the in-process lock of the Service. GitHub has no conditional write of an issue, so a parallel write can lose a mark today.
- **The implement job already runs in its own pod** (#2667), and a Service release does not stop it. Stage can follow the same path with no shared store.
- **The direction of the owner, 2026-11-11:** move as much Service work as possible to jobs, workflows and event-driven tools, and use a central Valkey store for shared data, for coordination and for the context of cold containers.

## Decision

### 1. The Service keeps only the webhook router

`roadmap-service` receives webhooks (ADR 0009), serves `/metrics` and serves the read-only API that #4581 records. At the end of tracker #4517 it runs no row and holds no volume. It runs 2 replicas with `RollingUpdate`, `maxUnavailable: 0` and a PodDisruptionBudget.

- For a subscribed event that has a scoped update, the router creates the intake unit of that issue.
- For another subscribed event, the router creates a sweep of that repository. When a sweep of the repository exists, the router sets the due mark of the sweep.
- During a hold (the GraphQL reset or the identity halt), the router creates nothing and sets a due mark.
- When the create fails, the router answers 202, sets the due mark and counts the failure.

### 2. Each job runs in a pod of its own

| Job | Unit of one pod | Trigger |
| :--- | :--- | :--- |
| stage | one Ready item | the sweep; a due mark from refine |
| refine | one item | the sweep; a due mark from intake |
| alternatives | one item | the sweep |
| intake | one batch of at most 5 candidates | the sweep |
| scoped intake | one issue | the router |
| metrics and the two status pages | all repositories | a schedule every 15 minutes |
| `brain-daily`: repair, signals, consolidate and evaluate (ADR 0023) | all repositories of the brain | a schedule at 02:30 UTC every day; the sweep, for the due mark `brain-repair` or `brain-consolidate`, with that task only, at most once a day for each mark |
| `brain-weekly`: aggregate and improve (ADR 0023) | all repositories of the brain | a schedule at 01:00 UTC every Monday |
| `resolve`: the question resolver (section 8) | at most 5 items of the repositories of the row | a schedule at minute 15 of every fourth hour, UTC (`15 */4 * * *`) |
| `group`: the families of items that a bot filed (section 8) | all families of the repositories of the row | a schedule at 03:45 UTC every day (`45 3 * * *`) |
| `split`, with its calibrate step (section 8) | at most 2 items of the repositories of the row | a schedule at minute 30 of every sixth hour, UTC (`30 */6 * * *`) |
| `watch`, which replaces the rows `stage_ready` and `pr_conflicts` (section 8); `release_comments`, `retitle`, the redelivery | steps of the sweep | the sweep |
| sweep | all repositories, or one repository for a hint | a schedule every 5 minutes; the router; a due mark |
| implement | one item, as the runner Job; one Workflow for each item with #3105 | the sweep |
| `fix-checks` (section 8) | one head and one failed check of a bot pull request | the sweep, for the due mark `fix-checks:<pr>` that `watch` sets |
| `fix-conflict` (section 8) | one base and one head of a bot pull request | the sweep, for the due mark `fix-conflict:<pr>` that `watch` sets |
| `fix-plan` (section 8) | one plan pull request with the label `plan/needs-fix` | until the sweep step, the row `fix_plan` of the model lane of the Service; then the sweep |

- **Only the router and the sweep create units.** No unit creates another unit, and no DAG chain links two jobs. A unit that makes more work due sets a due mark, and the next sweep creates the unit within 5 minutes.
- **One unit for each item.** Before a create, the creator lists the units of the repository by the labels of the repository, the job and the item. A template-level mutex for each item also stops a second pod. A unit name of at most 63 characters, fixed by its input, makes a repeated create get 409.
- **A unit judges its item again at its start.** It runs the full selection of its job, narrowed to one item, so every selection rule applies. The `--item` option stays for a person.
- **Only the sweep writes the last success of a job.** A unit writes its marks and its failure entry.
- **The sweep deletes a failed unit** when the failure ledger allows a retry, so a failed unit does not block its item.
- **The engine parts.** A WorkflowTemplate for each job. CronWorkflows with `schedules` for the sweep, the metrics, the two brain runs and the rows `resolve`, `group` and `split`; Argo v4.0 removed the singular `schedule`. `synchronization.mutexes` for the intake and implement jobs of each repository and for each item. The semaphores `agent`, `triage` and `steward` in the ConfigMap `roadmap-limits`. `retryStrategy` for faults of the infrastructure, and a deadline on each template.
- **`Strict`, not `Secure`.** Under `Secure`, a running Workflow fails when its WorkflowTemplate changes, and each release changes the image digest of the templates.
- **Before the engine step**, stage runs as a plain Job from a suspended CronJob template, as the runner Job of implement does. The Job list is its lock, and at most one stage Job runs at a time.
- **An agent pod has no API token** in its main container. It gets only the Secret keys that its job needs. The sweep runs as ServiceAccount `roadmap-service`. An admission policy admits from that account only units of the roadmap templates, with arguments only.
- **Each pod keeps the label `app.kubernetes.io/name: devops-cli-job`,** so the network policies of the stack and of the MCP server apply to it with no change.
- **Each pod mounts the ConfigMap of the Service** and sets one model call in flight at its entry point. A ConfigMap edit reaches the next pod and stops no running work.

### 3. Valkey holds the shared state, and GitHub stays the source of truth

- **A new instance, `valkey-roadmap`,** holds the coordination state: Valkey 9.1.3, AOF with `appendfsync everysec`, `noeviction`, a 2Gi `local-path` volume on the node of the sweep volume, three ACL users (`router`, `sweep`, `agent`) and ingress only from namespace `devops`. The three passwords are generated credentials of `devops k8s push-secrets`. `valkey-devops` stays the cache that can evict keys.
- **Rules.**
  1. Valkey holds a copy, a lock, a counter, a due mark, a cache or unfinished work. It never holds the only copy of a decision.
  2. A job reads GitHub before it writes GitHub. A Valkey value never replaces that read (ADR 0016).
  3. When Valkey and GitHub do not agree, GitHub wins.
  4. A lock makes the window of a lost update smaller, but it does not close it. Each job record write reads the record back, and writes again when a mark of its writer is missing. The guard of ADR 0016 covers the field labels only.
  5. A job that can post two times reads its marker before it posts.
  6. Each key has a TTL, or one owner that deletes it.
  7. No credential goes into Valkey. Each pod makes its own installation token.
  8. Each key name has a schema version. A change of a key shape writes a new key name, and the old key expires. No code reads both.
  9. A sentinel key shows that the store kept its data. When the sentinel is missing, each caller fails closed and an alert fires.
- **What moves to `valkey-roadmap`:** the request windows, the GraphQL hold, the identity halt, the delivery ids, the job record lock, the sweep lock, the schedules, the due marks, the intake record, the release ledger, the failure ledgers, and the stage plan records and refused replies.
- **What stays out of Valkey:** secrets and tokens, clones, the image, the uv cache and the AI spend ledger.
- **When `valkey-roadmap` does not answer,** no round starts: a pod waits 60 seconds, then exits with 75, and the engine tries it again. The router still accepts deliveries. The sweep still runs the deadline row of implement, so a Valkey outage does not end the runner Jobs.

### 4. One request budget for all pods

All pods of one App installation use one set of moving windows of the open library `limits`, with Valkey storage. One window is the self-cap of all requests in an hour (the setting `service.github_requests_per_hour`). Two windows stay below the secondary limits of GitHub for requests that make content: 80 a minute and 500 an hour. A 304 answer gets no refund, because in short pods it is about 0.25 percent of the answers. A pod checks the window before it takes a slot or a lock. When the window is near the cap, the sweep skips the jobs that are not urgent, metrics first. It does not wait.

### 5. Model calls across pods

Each pod keeps one model call in flight, set at its entry point. The owner set the limits on 2026-11-11. Before the engine step, at most one stage Job runs at a time. After the engine step, the semaphore `agent` admits 2 pods and the semaphore `triage` admits 2 pods. The semaphore `steward` admits 1 pod of the rows `resolve` and `split` (section 8). A person changes a limit with one ConfigMap edit. The Service model is a hosted route, so the reason for one slot in total (#2564) does not apply to it.

### 6. A cold pod gets warm from its image, its clone and Valkey

- **The image:** the dependencies go in their own layers before the project source (#4550). Then a release changes about 25 MB of layers, not about 0.5 GB. A pre-pull DaemonSet comes only if a pull stays slow after that.
- **The pod:** a blobless clone (`git clone --filter=blob:none`) and local wheels for uv (`UV_FIND_LINKS`).
- **Valkey:** the coordination state and the plan record, so a pod needs no volume and no other pod.

Valkey does not hold the image, the clone or the uv cache. Those take 70 to 90 percent of the time of a cold start. A shared store of GitHub answers comes only if a probe shows that a new installation token gets 304 for an ETag that another token got. A stage checkpoint comes only if stage pods stop for causes other than a rollout.

### 7. The order of the steps

The child items of tracker #4517 go in this order. Each step deletes the Service path that it replaces, with no shim.

1. The cheap fixes: intake due on a new issue (#4540), the image layers (#4550) and the read-back repair of job records (#4555).
2. This record, and the stage Job (#4559).
3. The Valkey steps (#4563, #4564, #4565).
4. The engine (#4566).
5. The other jobs: intake (#4567), refine (#4568), alternatives (#4573) and implement (#3105).
6. The sweep (#4574), and then the stateless router (#4575).

### 8. The steward rows and the step rows

The issue stewards of tracker #4780 add the rows `resolve`, `group` and `split`. The step jobs of tracker #5014 add the rows `watch`, `fix-checks`, `fix-conflict` and `fix-plan`. These rows take work that waits for a person, and the work of a finished pull request, out of the producer jobs.

#### Rules of these rows

1. In the job record and in the comments, a row writes only its own keys and its own marked comments.
2. A model verdict only flags. It never closes an item, and it never marks a pull request ready.
3. Valkey holds only due marks, ledgers and caches for these rows. The GitHub job record stays the source of truth (section 3).
4. No row starts another row, and no coordinator exists. A row that makes work due sets a due mark, and the sweep creates the unit (section 2).
5. Each row has the mode `off`, `plan` or `on` in `roadmap.<row>.mode`, with `_` in place of each `-` of the row name. Mode `plan` writes the plan to the log and nothing to GitHub. Mode `off` is the stop switch. The new rows `resolve`, `group`, `split`, `fix-checks`, `fix-conflict` and `fix-plan` start in mode `plan`. The row `watch` starts in mode `on`, because it replaces the live rows `stage_ready` and `pr_conflicts`, and the work of those two rows must not stop.
6. A row reads its marker before it writes (section 3, rule 5). GitHub state is the first marker: the head commit, the draft flag, the merge state and the open pull request of a head and a base.
7. Each limit is shorter than the limit of the call around it, so the inner limit stops first.
8. The CronWorkflows of `resolve`, `group` and `split` are not units, as for `brain-daily`. So the rule "Only the router and the sweep create units" stays. Before the engine step (#4566), a person or an agent runs the command of each of these rows.

#### `resolve`: the question resolver

- **Selection.** For each repository of `roadmap.resolve.repos`, the open items with an open question: `refine.next_step` is `person`, the judge refused the item, a criterion is "Pending a person", the record holds `stage.pending`, or a trusted author asked a question that has no later reply.
- **Skips.** Blocked and started items, `owner/*` claims, untrusted authors, trackers and the members of a group. Also an item that a person edited or that the row answered in the last 24 hours, an item that refine read in the last 15 minutes, and an item with the same input hash.
- **Order.** The priority, then the count of the items that the item blocks, then the age of the wait.
- **Work.** Rules class each question first: a form question, a wait for a date or an event, a step of a person after the merge, or an owner-only question. For the other questions, one agent run for each item uses the read-only investigation tools of refine at a pinned commit. An answer stays only with a verified source. An owner-only question gets the recorded owner decision as a quote, or one frame with options and a recommendation. The decision point `resolve.question_class` (ADR 0020) runs in `shadow`.
- **Trigger.** CronWorkflow `roadmap-resolve` with the schedule `15 */4 * * *` (UTC), `concurrencyPolicy: Forbid`, the mutex `resolve` and the semaphore `steward`.
- **Bounds.** 5 items a run, 6 questions an item, 60 tool calls and 400,000 tokens an item, and 0.10 USD a run. The limits are tool call 30 s < model call 300 s < item 600 s < run 3,000 s < `activeDeadlineSeconds` 3,600 s < schedule period 14,400 s.
- **Marker.** `<!-- devops roadmap resolve -->`. The record keys are `resolve.input_hash`, `resolve.answers` (the question hash, the class, the answer hash and the sources of each answer), `resolve.owner_asked`, `resolve.commented_at` and `resolve.failed_*`.
- **Idempotency key.** The input hash of the item. The row posts a comment only when the answers hash changes, and one owner frame for each question hash across all items.
- **Valkey.** No key.

#### `group`: the families of items that a bot filed

- **Selection.** The open New and Ready items that a bot filed, with a fingerprint: the filer, the masked title template and the first stable key (a rule id, an alert, a path or a set of declared surfaces). Two or more open members with one fingerprint make a family. The judge of `brain-daily` (#4687) keeps the items that a person filed.
- **Skips.** Started items, items with a milestone or an `owner/*` claim, trackers, the parts of a split, declined group ids, and the members that a person opened again.
- **Work.** For each member, the row runs the re-check of its producer from a registry: the hardening report, the state of the code-scanning alert, or the latest run of a workflow on the default branch. A pass closes that member as not planned, and the comment gives the output of the re-check. Two or more members that fail get a blocked-by link to one anchor, and the anchor gets one comment. When the anchor closes, each member gets its own re-check again. A merge into the anchor stays the `consolidate --apply` of a person (#3743).
- **Trigger.** CronWorkflow `roadmap-group` with the schedule `45 3 * * *` (UTC) and the semaphore `triage`.
- **Bounds.** 0 model calls and at most 5 closes a run. The row never closes an item with a milestone, an `owner/*` claim or a start. The limits are run 1,500 s < `activeDeadlineSeconds` 1,800 s.
- **Marker.** `<!-- devops roadmap group -->`. The record keys are `group.id`, `group.anchor` and `group.check`.
- **Idempotency key.** The group id and the facts of its members. A run with the same facts writes nothing. When a person opens a closed member again, that decision is final.
- **Valkey.** No key.

#### `split`: the parts of an item that is too large

- **Selection.** An item with `stage.needs_split` or `refine.needs_split`, a refine split that nobody applied, or a stop for its size above the fitted threshold. A stop for size is one of these: a stage `plan_defect` or `parser` failure two times on one text hash, a refused plan, an implement stop (`limit_reached`, `timeout`, `plan_defect`, `no_change_in_fix` or no repair rounds left), a suspend of the failure ledger, or no progress after the fitted stall age.
- **Skips.** First the row removes the causes `ci_infra`, `provider`, `refused_tool` and `conflict`, an open dependency and a wait for a person. It skips trackers, started or claimed items and declined split ids. An item with a milestone gets the plan comment only.
- **Work.** One split call (`stage_split.py`) and at most 1 repair. Then checks with no model: each criterion of the parent goes to one part, each part is below the threshold, and the order has no cycle. Intake files 2 to 5 parts with `Split from #N.` and the `#N` dependencies, and each part becomes a sub-issue of the parent. One comment on the parent gives the measured reason with n and the window.
- **Calibrate.** A step of the run when the cached thresholds are older than 7 days, with 0 model calls. It fits the thresholds from the job records and the OpenSpec change folders with statsmodels. A side with fewer than 30 samples uses the default, and the result says so.
- **Trigger.** CronWorkflow `roadmap-split` with the schedule `30 */6 * * *` (UTC) and the semaphore `steward`.
- **Bounds.** 2 items a run, 5 parts an item, 10 parts a day, 300,000 tokens an item and 0.05 USD a run. The limits are model call 300 s < item 900 s < run 2,400 s < `activeDeadlineSeconds` 3,000 s.
- **Marker.** `<!-- devops roadmap split -->`. The record keys are `split.input_hash`, `split.parts` and `split.filed_at`.
- **Idempotency key.** The input hash: the failure classes, the size and the text hash. The row files the parts one at a time and records each part after its create, so a run after a stop files only the missing parts. It posts the comment only when no split comment holds the same hash of the parts.
- **Valkey.** `roadmap:v1:split-thresholds:<owner>/<name>`, a cache with a TTL of 8 days. The job records stay the source.

#### `watch`: the state of each roadmap pull request

- **Selection.** The open pull requests of the repository that a roadmap job opened or that deliver an item: a plan pull request that a record names in `stage.pr`, and a pull request into the default branch whose body closes exactly one open item.
- **Skips.** A pull request whose item has a live unit.
- **Work.** One pure function gives a verdict for each pull request: PENDING, READY, FAILED with the class of the check, CONFLICT, BEHIND, MERGED or CLOSED. The function `due_steps` routes the verdict as the table below shows. The sweep uses the same function for its reconcile.
- **Trigger.** A step of the sweep. Until the sweep step (#4574), a row of the status lane of the Service in the place of the rows `stage_ready` and `pr_conflicts`, which it replaces. A `pull_request` event makes it due sooner (#4413).
- **Fix due marks.** `watch` sets the due mark of a fix row only when that row exists (#5027, #5028) and its mode is `plan` or `on`. Until the fix row is in mode `on`, a verdict of a bot pull request that goes to that row also gets the route of a pull request of a person. Thus a bot pull request with a conflict gets one comment for each head, as the row `pr_conflicts` did.
- **Bounds.** 0 model calls. One GraphQL query for each repository and tick, and REST with ETags during a GraphQL hold. The limits are request 30 s < one pull request 60 s < row 240 s < tick 300 s.
- **Marker.** `<!-- devops roadmap watch -->` on its one comment for each head. A ledger holds the pull request, its head, its verdict and the time of its next read. The ledger is a cache: GitHub holds the head, the draft flag and the merge state.
- **Idempotency key.** The pull request and its head commit. The step `ready` reads the draft flag and the expected head before it marks a draft ready. A due mark has one name for each pull request, so a second set changes nothing.
- **Valkey.** When the ledgers move to `valkey-roadmap` (section 3), the ledger is `roadmap:v1:watch:<owner>/<name>`, with the row as its one owner. Until then it is a file beside `schedule.json`.

| Verdict | Bot pull request | Pull request of a person |
| :--- | :--- | :--- |
| PENDING | Read again. A failed head only after a change of the head or the base, or after 30 minutes. | The same |
| READY | The step `ready`. A plan gets `stage.ready`, and a delivery gets In Review. | Nothing. A person runs `devops pr ready`. |
| FAILED: test, lint, types or plan check | The due mark `fix-checks:<pr>` while rounds are left, else Blocked | Nothing |
| FAILED: `ci_infra` | One comment, then a wait | Nothing |
| CONFLICT | The due mark `fix-conflict:<pr>` | One comment for each head |
| BEHIND, with no conflict | Nothing: no update of a branch that only catches up | Nothing |
| MERGED or CLOSED | The Status writer, and `cleanup` for a plan | The Status writer |

#### `fix-checks` and `fix-conflict`: one fix round for a finished bot pull request

- **Selection.** One bot pull request, from the due mark that `watch` sets. The App made the head of a bot pull request, and no person pushed a commit after the last push of the App. Its item has no claim of an agent or a person.
- **Stops.** The unit judges the pull request again at its start (section 2). It stops when the item gets the claim `owner/agent` or `owner/human`, or when the head is not the head that `watch` judged.
- **Trigger.** The sweep reads the due mark and creates the unit. Until the sweep step (#4574), the poll of the Service does this. Until the fix units exist (#5027, #5028), the runner Job calls the same step in its own loop, and no fix unit exists.
- **Unit.** Before the engine step, a Job from the suspended CronJob `devops-cli-runner` with arguments only, which the admission policy admits now. After the engine step, a Workflow from a WorkflowTemplate.
- **Order.** A fix unit counts against the limit of model pods (section 5). The creator puts it before a new implement or stage unit.
- **Spend.** Each fix row runs 1 week in mode `plan` first. Mode `on` needs the spend decision of the owner on tracker #5014: at most 4,000,000 tokens for each `fix-checks` unit, 2,000,000 for each `fix-conflict` unit, and 20 fix units a day for each repository. Tier 1 uses 0 tokens.
- **Deadline.** The deadline of a unit is the sum of its step limits plus at least 300 s, because the start of a pod takes up to 108 s.
- **Valkey.** No key.

| Part | `fix-checks` | `fix-conflict` |
| :--- | :--- | :--- |
| Selection | A failed check of the class test, lint, types or plan check. A `ci_infra` failure gets no unit. | The verdict CONFLICT |
| Tier 1, no model | `ruff check --fix`, `ruff format`, `devops docs generate` or `uv lock`, then the check again | When only archive paths conflict (`openspec/specs/**`, `openspec/changes/archive/**`): drop the archive commit, rebase the rest and archive again from the change folder. A generated document or `uv.lock`: take the default branch and generate again. A release path stops the unit. |
| Tier 2, model | One fix step, only when the log names a path of the plan scope. A plan draft gets the stage plan repair in its change folder. | One fix step with only the paths that still conflict, both sides and the plan scope |
| Before the push | The check again | `openspec validate --specs --strict` and the scoped checks |
| Rounds | Soft cap 3 for each pull request (`roadmap.implement.repair_rounds`), 1 more while the count of errors falls, hard cap 5 | One model round for each base and head. Soft cap 2 for each pull request, 1 more while the count of conflicted files falls, hard cap 4 |
| Heads | At most 3 for each pull request | At most 3 for each pull request |
| Limits | log 60 s < fixers 300 s < model request 1,200 s < model step 1,800 s; checks 1,800 s; push 300 s | fetch 30 s < rebase 120 s < generate 600 s < model request 1,200 s < model step 1,800 s; checks 1,800 s; push 300 s |
| Marker | `<!-- devops roadmap fix-checks -->`. Record keys `fix_checks.key` (`<head>:<check>`), `fix_checks.rounds`, `fix_checks.errors` and `fix_checks.result`. | `<!-- devops roadmap fix-conflict -->`. Record keys `fix_conflict.key` (`<base>:<head>`), `fix_conflict.rounds`, `fix_conflict.files` and `fix_conflict.result`. |
| Idempotency key | The unit name from `<pr>:<head>:<check>` (ADR 0022), so a second create gets 409 | The unit name from `<pr>:<base>:<head>` |

#### `fix-plan`: one repair of a plan pull request with open findings

- **Selection.** An open draft plan pull request that holds `plan/needs-fix` and that the record of a Staged item names in `stage.pr`. The item has no runner Job and no claim of an agent or a person. The branch holds only commits of the App.
- **Stops.** The step judges the pull request again at the start of an attempt. It stops before any write when the head moved after the read or holds a commit of another author.
- **Work.** The open findings of the last plan comment of the item: the stage comment, or the comment of an attempt that kept the label, of a trusted author. With no such finding, one model review of the plan of the head at the latest default branch. With an open finding, one repair by the stage planner with that plan as `previous` and the open findings as `problem`, then the normal verification repair rounds of the stage job. A revision with fewer open findings is one commit on the latest default branch, pushed with `--force-with-lease` on the head that the step read. The label goes when no open finding remains.
- **Trigger.** Until the sweep step (#4574), the row `fix_plan` of the model lane of the Service, after `stage`, every 53 minutes and on a first run.
- **Bounds.** 1 plan a round, 2 attempts on each head, 6 hours between two attempts of one item, and 3 revisions for each pull request. An attempt has the model limits of one stage item, plus one review and one repair of the plan of the head. No attempt starts while the Service stops.
- **Marker.** `<!-- devops roadmap fix-plan -->` on one comment of the issue for each attempt that changes the plan or the label. The record keys are `fix_plan.key` (`<pull>:<head>`), `fix_plan.attempts`, `fix_plan.revisions`, `fix_plan.at` and `fix_plan.result`. The step writes the key, the count and the time before its first model call. It does not edit the stage comment.
- **Idempotency key.** The pull request and its head commit. The lease refuses a push when the head moved.
- **Mode.** `roadmap.fix_plan.mode`, which starts in `plan`.
- **Valkey.** No key.

#### `push` and `open` are steps, not units

`push` and `open` run inside the unit of their producer: stage, implement, `fix-checks` and `fix-conflict`. They have no row and no unit name.

- `push` holds the latest default branch at each push, refuses a push that only catches up, and pushes with `--force-with-lease` on the head that its caller saw.
- `open` reads the open pull request of the head and the base before it creates one.
- After the engine step, each can be a step template in the Workflow of its producer.

A step is one part of a job that runs the same way each time. Each step is one module and one command, `devops roadmap step <name>`, and every caller uses it. A step writes one JSON result line (#4845). It exits 0 when it is done or has nothing to do, 1 for a typed stop and 75 to try again later, and only exit 75 gets a retry. With `--dry-run` it sends no request. A short step, such as `watch` or `ready`, stays in the sweep, because a pod for each tick costs more than the work.

#### The trigger transport stays

Due marks and the sweep stay the transport between rows, and no dispatcher exists. The rejected option "A Valkey stream as the trigger queue" stays, and so does the audit stream rule of ADR 0023 section 4.

The pull request of #4792 read the source of Argo Events v1.9.11, the newest release (2026-07-13). Two facts of the old rejected option were not correct:

- **GitHub App webhooks.** A `GithubEventSource` takes the credentials of a GitHub App: the field `githubApp` holds the App id, the installation id and the private key ([`eventsource_types.go:751-758`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/apis/events/v1alpha1/eventsource_types.go#L751-L758), [`:813-815`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/apis/events/v1alpha1/eventsource_types.go#L813-L815)). It creates a hook only with a token or App credentials and a URL ([`:849-851`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/apis/events/v1alpha1/eventsource_types.go#L849-L851)). With only the webhook secret, it takes the deliveries of an existing hook and checks their HMAC ([`start.go:228-236`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/eventsources/sources/github/start.go#L228-L236), [`:378-380`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/eventsources/sources/github/start.go#L378-L380)).
- **Three replicas.** A JetStream EventBus has 3 replicas by default ([`jetstream_eventbus.go:11-13`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/apis/events/v1alpha1/jetstream_eventbus.go#L11-L13), [`:90-95`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/apis/events/v1alpha1/jetstream_eventbus.go#L90-L95)). The check of the EventBus also accepts 1 replica ([`validate.go:35-36`](https://github.com/argoproj/argo-events/blob/v1.9.11/pkg/reconciler/eventbus/validate.go#L35-L36)).

The decision stays. The router stays (section 1), so Argo Events is a second receiver with a second HMAC check, own-write refusal, hold check and scoped table. It adds at least 4 pods that run all the time: the controller ([`install.yaml:389-391`](https://github.com/argoproj/argo-events/blob/v1.9.11/manifests/install.yaml#L389-L391)), one JetStream replica, the EventSource and the Sensor. It does not stop a lost delivery, because GitHub does not send a failed delivery again by itself (Context). The sweep finds that work.

Look at Argo Events again when one of these conditions occurs:

- the router goes away;
- a second event producer comes, other than the GitHub hooks;
- the event table of the router changes one or more times each month.

## Considered Options

- **Plain Jobs and CronJobs with Valkey locks and slots** (the no-go path): not taken, because the verdict is go. The engine adds a queue behind each mutex and semaphore, retry expressions, `Strict` template checks and a UI, with no code of ours.
- **Keep each job in the Service, with a longer drain or Argo CD sync windows**: rejected. A drain or a window cannot wait for a round of up to 109 minutes, and a window also delays the fixes of the whole Application.
- **DBOS durable workflows in the Service process** (the runner-up of ADR 0008): rejected. A step can continue after a restart, but the work stays in the pod that each release restarts, and DBOS needs Postgres.
- **Move all shared state to Valkey before a job leaves the pod**: rejected. Stage needs no shared store to run as a Job (#2667), and restarts stop stage most.
- **WorkflowEventBinding**: rejected. It needs argo-server with at least two replicas and a public route, and it does the HMAC check, the own-write refusal and the scoped table of the router a second time.
- **Argo Events**: rejected, as in ADR 0008. It is a second receiver beside the router, with at least 4 more pods, and a lost delivery stays lost (section 8).
- **KEDA ScaledJobs on a Valkey stream**: rejected. Three more Deployments and one ScaledJob for each lane of each repository, to replace one `create` call.
- **A Valkey stream as the trigger queue**: rejected. The due marks and the sweep find each lost trigger within 5 minutes.
- **DAG chains between jobs**: rejected. A DAG task does not hold the unit name, so the sweep can start a second pod for the same item, and the deadline of the first job cuts the second.
- **Deterministic names as the only rule of one unit for each item**: rejected. A new plan key gives a new name while the old unit runs.
- **The poll as a timer in the router**: rejected. Two router replicas poll two times, or need leader election.
- **One unit for each job of each repository on each tick**: rejected. About 2,300 pods a day for the sweep alone, and most of them find no work.
- **`valkey-devops` or `valkey-runs` for the state**: rejected. The first evicts keys and keeps no file. Any source can reach the second on a NodePort.
- **A Kubernetes Lease for each lock**: rejected. Each renewal is an API write, and agent pods hold no API token.
- **A hand-built Lua window with a 304 refund**: rejected. In short pods the refund saves about 0.25 percent of the requests, and `limits` also covers the secondary limits.
- **A lock as the only guard of a job record**: rejected. A lock can expire or go away, and GitHub gives no fence.
- **One shared installation token in a Secret, so that pods share ETags**: rejected. Each agent pod then holds a token for each repository, not for one.
- **A pre-pull DaemonSet as the first image fix**: rejected. It moves about 50 GB a day from the registry and treats a symptom of the layer order.
- **`templateReferencing: Secure`**: rejected. Each release fails the running Workflows.
- **Clones, the image or the uv cache in Valkey**: rejected. Bulk files belong on a node, in the image or on a volume.

## Consequences

- A release or a ConfigMap edit no longer stops a model round. At the end of the tracker, a release no longer stops the webhook receiver.
- Each job must stay safe to run two times. The read-back repair of job records, the markers of the jobs that post, the rule of one unit for each item and the "not placed" marks of the intake record keep it safe. A test stops each job after each GitHub write and runs it again.
- The cluster runs about 1,000 to 1,200 short pods a day. The measurement gives 56 to 78 API-server requests for each Workflow, about 10 percent more requests. Each short pod adds about 76 metric series, so the engine step sets a series budget and drops the labels of each pod.
- The row and lane metrics of the Service go away. Each pod sends its metrics by OTLP. Alerts come for a stale sweep, the controller, failed units and a queue that waits. The six Service alerts that read lane labels change in the step that removes those labels.
- Pods of more than one image digest share the Valkey keys during a release. The versioned key names keep them apart. The requests can go above the self-cap for one deadline while two windows exist, and the headers of GitHub still pace the real limit.
- The PVC `roadmap-service-home` and its clones move from the Service to the sweep and the metrics pod. The sweep and `valkey-roadmap` run on the node of that volume, so the loss of that node stops the sweep and the shared state together.
- The items that add the passwords of `valkey-roadmap` register them as generated credentials. After each such item merges, a person runs `devops k8s push-secrets --plan` and then `devops k8s push-secrets`. A person clears an identity halt with a command in the router pod.
- The Valkey fake gets a contract suite and the `lua` extra of fakeredis (#4557) before the first step that uses a lock or a window, because the fake refuses `EVAL` today.
- The engine step changes CronWorkflow `rag-ingest` to `schedules`, because the controller watches `devops` from that step on. It also adds a kustomize fieldSpec for the image of a WorkflowTemplate, because without it the image override of Image Updater does not reach a template.

## Status History

Amended on 2026-11-11 by [ADR 0023](0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md). The unit table gets the rows `brain-daily` and `brain-weekly`. A CronWorkflow is not a unit, so the rule that only the router and the sweep create units stays.

This record amends ADR 0003, ADR 0008, ADR 0009 and ADR 0017. The Status section gives each change.

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md` names the merge commit.

The pull request of #4792 amends this record on 2026-11-12. It adds section 8 and six rows: `resolve`, `group` and `split` of tracker #4780, and `watch`, `fix-checks` and `fix-conflict` of tracker #5014. It adds the semaphore `steward`, and it corrects the facts about Argo Events. The merge of that pull request is the approval of the six rows and of the semaphore.

The pull request of #5056 amends rule 5 of section 8 on 2026-11-12. Only the five new rows start in mode `plan`. The row `watch` starts in mode `on`, because it replaces the live rows `stage_ready` and `pr_conflicts`. Until a fix row is in mode `on`, `watch` also routes the verdict for that row as for a pull request of a person.

The pull request of #5061 amends this record on 2026-11-12. It adds the row `fix-plan` of tracker #5014 to section 2 and section 8. The merge of that pull request is the approval of the row.

The verdict of ADR 0008 is go. The owner recorded "warm p95 11 s - go" on [#1535](https://github.com/dan-petty/devops-cli/issues/1535#issuecomment-6787508710) on 2026-11-11, after the [measurement](https://github.com/dan-petty/devops-cli/issues/1535#issuecomment-6787453030) of the same day:

| Measure | Value | Limit of ADR 0008 |
| :--- | :--- | :--- |
| Warm p95, from creation to Succeeded | 11 s | at most 30 s |
| Cold run, image pull included | 54 s | reported apart |
| Burst p95, 20 Workflows at one time | 24 s | not used |
| New 429 or 5xx answers of the API server in the burst | 0 | must be 0 |
| Failed submissions | 0 of 40 | not used |
| API-server requests for each Workflow | 56 (burst) to 78 (sequential) | not used |

So the engine is Argo Workflows, and this record has no plan for a no-go. It amends four records:

- **ADR 0008.** (1) Stage moves to a plain Kubernetes Job on the path of #2667 before the engine step, as implement did. The engine step then moves stage to a WorkflowTemplate. (2) The child items of tracker #4517 replace steps 2-6 of #1535. (3) Workflows run in namespace `devops`. The controller runs with `--namespaced --managed-namespace devops` and gets a Role in `devops`. This is a third option beside the two of "One namespace watched": it needs no ClusterRole and no copy of Secret `devops-cli`. (4) The controller sets `workflowRestrictions.templateReferencing: Strict`.
- **ADR 0003.** The poll becomes the sweep: a cluster schedule every 5 minutes, not a timer in the Service. The intervals of the rows round up to 5-minute ticks. The sweep stays the source of truth. A short row asks GitHub to redeliver each delivery that failed (#4560). This row cuts the delay of a delivery that a rollout lost, and it is not a second source of truth. The consequence about "both of a repository's lanes" no longer applies, because no lane stays.
- **ADR 0009.** The delivery target of the roadmap consumer creates a unit of work or sets a due mark. It does not put a trigger on a lane. The router records a delivery id only after the create succeeds or gets 409. The stateless router step (#4575) deletes the Mattermost provider and its `/roadmap` command: the owner decided this on 2026-11-11, after 0 uses in 7 days. Each other rule of ADR 0009 stays.
- **ADR 0017.** A scoped update runs in a pod of its own under the intake mutex of its repository, not on a lane. Intake is also due when a new issue opens (#4540), so a lost scoped update waits at most one sweep. The table and the lane rule of ADR 0017 name the model lane for scoped intake, but the code uses the triage lane (`SCOPED_UPDATES` in `src/devops_cli/roadmap/run.py`). The poll rule of ADR 0017 gives 151 seconds. That is the default of `service.poll_interval_seconds`, and the live ConfigMap sets 300 seconds. This record corrects those three places, and the text of ADR 0017 stays as it was. Each other rule of ADR 0017 stays: a scoped update writes no last success, and it records what it decided.

ADR 0001, ADR 0015 and ADR 0016 stay as they are. GitHub stays the source of truth.

The naming record of #4533 owns the object names, the labels, the Valkey key forms, the mutex names and the service names that this record uses. Until that record merges, tracker #4517 holds those rules. The pull request that merges second adds the link between the two records.

2026-11-12: Living detail moved to tracker #4517 (the step order), to the OpenSpec change of each new row, and to [ADR 0022](0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md) (the names) (#4617).

2026-11-12: Fact out of date: section 8, row `fix-plan`, Work and Marker. [The fix-plan step](../roadmap/stage.md#the-fix-plan-step) holds the results and the read before the marks (#5213).

2026-11-13: Fact out of date: section 8, row `fix-plan`, Marker. [The fix-plan step](../roadmap/stage.md#the-fix-plan-step) holds the keys `fix_plan.version` and `fix_plan.evicted` and the kill classes (#5413).
