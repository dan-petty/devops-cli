# The roadmap Service is a webhook router, cluster pods run the roadmap jobs, and Valkey holds their shared state

This record amends ADR 0003, ADR 0008, ADR 0009 and ADR 0017. The Status section gives each change.

The roadmap Service runs every roadmap job in one pod. About 19 releases and ConfigMap edits a day restart that pod. Each restart stops the rounds that run in it, and a stage round runs for 21 minutes at the median. This record moves each job out of the Service pod into a pod of its own on Argo Workflows, and it moves the state that the jobs share into Valkey. The Service keeps only the webhook router.

## Status

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md` names the merge commit.

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
| `stage_ready`, `release_comments`, `retitle`, the redelivery | steps of the sweep | the sweep |
| sweep | all repositories, or one repository for a hint | a schedule every 5 minutes; the router; a due mark |
| implement | one item, as the runner Job; one Workflow for each item with #3105 | the sweep |

- **Only the router and the sweep create units.** No unit creates another unit, and no DAG chain links two jobs. A unit that makes more work due sets a due mark, and the next sweep creates the unit within 5 minutes.
- **One unit for each item.** Before a create, the creator lists the units of the repository by the labels of the repository, the job and the item. A template-level mutex for each item also stops a second pod. A unit name of at most 63 characters, fixed by its input, makes a repeated create get 409.
- **A unit judges its item again at its start.** It runs the full selection of its job, narrowed to one item, so every selection rule applies. The `--item` option stays for a person.
- **Only the sweep writes the last success of a job.** A unit writes its marks and its failure entry.
- **The sweep deletes a failed unit** when the failure ledger allows a retry, so a failed unit does not block its item.
- **The engine parts.** A WorkflowTemplate for each job. CronWorkflows with `schedules` for the sweep and the metrics; Argo v4.0 removed the singular `schedule`. `synchronization.mutexes` for the intake and implement jobs of each repository and for each item. The ConfigMap semaphores `agent` and `triage`. `retryStrategy` for faults of the infrastructure, and a deadline on each template.
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

Each pod keeps one model call in flight, set at its entry point. The owner set the limits on 2026-11-11. Before the engine step, at most one stage Job runs at a time. After the engine step, the semaphore `agent` admits 2 pods and the semaphore `triage` admits 2 pods. A person changes a limit with one ConfigMap edit. The Service model is a hosted route, so the reason for one slot in total (#2564) does not apply to it.

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

## Considered Options

- **Plain Jobs and CronJobs with Valkey locks and slots** (the no-go path): not taken, because the verdict is go. The engine adds a queue behind each mutex and semaphore, retry expressions, `Strict` template checks and a UI, with no code of ours.
- **Keep each job in the Service, with a longer drain or Argo CD sync windows**: rejected. A drain or a window cannot wait for a round of up to 109 minutes, and a window also delays the fixes of the whole Application.
- **DBOS durable workflows in the Service process** (the runner-up of ADR 0008): rejected. A step can continue after a restart, but the work stays in the pod that each release restarts, and DBOS needs Postgres.
- **Move all shared state to Valkey before a job leaves the pod**: rejected. Stage needs no shared store to run as a Job (#2667), and restarts stop stage most.
- **WorkflowEventBinding**: rejected. It needs argo-server with at least two replicas and a public route, and it does the HMAC check, the own-write refusal and the scoped table of the router a second time.
- **Argo Events**: rejected, as in ADR 0008. It adds NATS JetStream with three replicas, an EventSource and a Sensor, and it does not take GitHub App webhooks.
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
