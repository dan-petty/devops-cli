# Proposal: #5553

## Why

#5553: the Service runs three lanes for each repository, and each lane runs one round at a time (`service_jobs` in `src/devops_cli/roadmap/run.py`). The model lane runs `retitle`, `stage`, `fix_plan`, `refine` and `alternatives` one after the other. A stage round takes 36 to 100 minutes, and in that time no refine, retitle or alternatives round of the same repository starts. On 2026-11-13 the devops-cli refine row had no round from 18:01Z to 20:14Z while stage #5448 ran. The backlog intervals of #5470 cannot help a row that waits for another row.

The owner asked on 2026-11-13 for a lane for each Service job, and for jobs that run async and are ready for event-driven triggers.

## What Changes

- Each row of `DEFAULT_DUE_TABLE` runs in a lane of its own: one worker and one trigger queue for each row and repository. The name of the lane is the name of the row. Lanes do not wait for each other.
- The new setting `service.lanes` puts rows into a shared lane, for example `{model: [stage, refine]}`. A row that no lane names keeps its own lane. The rows of a lane run in the order of the table. The Service reads the setting when it starts, so a change needs a restart. The Service refuses an unknown row, a row in two lanes, and a lane name that is the name of a row in another lane.
- Each lane that has a row that needs files works in a clone of its own, `<repo dir>/lanes/<lane>`, so no two lanes share a working tree. The clone contract of `ensure_checkout` does not change. When the Service starts, it removes the clones and the snapshots of lanes that it does not run, and the clones of the three earlier lanes (`clone`, `model-clone`, `triage-clone`).
- Each lane reads every issue through a listing snapshot of its own, `listing-<lane>` in the state directory, and its worker is the one writer. The lane that holds `intake` reads through the intake snapshot `listing`, as the scoped intake does on the same worker.
- A scoped update runs on the lane that holds its row. When it wakes other rows, it sends its trigger to each other lane of the repository.
- A trigger can carry a subject, the number of the issue that the event is about. A batch holds the subjects of its triggers (`TriggerBatch.subjects`). No row reads them yet: #5555 routes events to lanes by subject.
- `devops_cli_roadmap_row_seconds` gets the attribute `lane` in a Service round. The span of a round and `devops_cli_service_jobs_total` already carry the lane.
- The shared limits of the pod do not change: the model call semaphore `service.model_call_concurrency`, the budget `service.github_requests_per_hour`, the failure ledger and the round pause. The store keeps its optimistic write check (`RoadmapItemChangedError`, class `head_moved`) and its process lock from the read to the write of a job record.
- The behavior of the Service changes, so the change carries spec deltas.

## Capabilities

### New Capabilities

- `roadmap-service-lanes`: the lanes of the Service, the setting `service.lanes`, the clone and the snapshot of each lane, and the subject of a trigger.

### Modified Capabilities

- `roadmap-implement-job/runner-job`: a round of another lane does not delay the row `implement`.
- `roadmap-intake-listing`: each lane reads through a snapshot of its own.
- `roadmap-scoped-updates`: a scoped update runs on the lane of its row and wakes each other lane.
- `metric-instruments`: the row seconds histogram carries the lane in a Service round.

## Impact

- `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/`.
- Deleted: the constants `CONST_SERVICE_LANE_STATUS`, `CONST_SERVICE_LANE_TRIAGE`, `CONST_SERVICE_LANE_MODEL` and `CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME`, the field `ScopedUpdate.lane`, and the parameter `clone_dirname` of `service_job`.
- Workers: 14 lanes for each repository in place of 3, so 98 worker threads for 7 repositories in place of 21. Each poll starts a round on each lane. A round with no due row sends no GitHub request, and the budget sets the poll interval from the mean cost of a round, so the requests of a poll do not change.
- Disk and memory: see the design. No manifest changes: the limits hold the measured and the expected use.
- This change fits one pull request.

## Feasibility

- Source at `origin/main` (0ae1ce51f): `service_jobs` returns three lanes, `RepoWorker` runs one queue for each lane and repository, and `ServiceManager` makes one worker for each name in `jobs`. So the engine runs any number of lanes, and only the table of lanes changes.
- Live pod, 2026-11-13: memory 744 MiB now (`kubectl top`), largest working set of one pod in 3 days 1459 MiB, limit 3 GiB. Volume use 588 MB: the two devops-cli clones take 392 MB (`clone` 206 MB, `model-clone` 187 MB), and each devops-cli snapshot is 27 MB. The claim is 1 GiB of class `local-path`, which does not hold a volume to its size and cannot grow a claim in place (`k8s/README.md`).
- git 2.47.3 in the image. A test with two `git worktree`s of one clone that fetch 40 times each while the remote moves 300 branches: 4 of 80 fetches failed with `cannot lock ref 'refs/remotes/origin/main': is at <a> but expected <b>`, and 6 of 80 failed with `core.filesRefLockTimeout` and `core.packedRefsTimeout` at 30000. The rows fetch inside their rounds (`stage`, `fix_plan`, `clone_git`, `worktree_add`), so a lock in the checkout cannot hold them. A clone for each lane has refs of its own.
- A fresh devops-cli clone is 152 MB (52 MB `.git`, 101 MB files), a blobless clone 129 MB, and a worktree 101 MB.
- The parse of the devops-cli snapshot takes 90 MiB for the first copy in a process and 45 MiB for each other copy.
- The new test of a blocked stage round fails on the base: refine waits in the model lane behind stage.

## Existing Tool Considered

- The Service already has the tool: `RepoWorker` is a thread worker with a trigger queue, and `ServiceManager` runs one for each lane and repository. The change adds no queue library. Celery, RQ, Dramatiq and arq need a broker process, and the move of jobs to cluster units (#4559, #4567, #4568, ADR 0021) replaces the in-pod workers later. A lane then only submits and watches its unit.
- `git worktree` (git 2.47.3): rejected for this use, with the measurement above. `git clone --reference` and `--shared`: rejected, because git documents that a borrowed object store loses objects when the reference repository prunes them.
- `IncrementalListing` and `FileSnapshotStore` of #4448 and #4854: reused for each lane.
- Cost: about 600,000 tokens and 1 day to build; about 10,000 tokens a month to keep and fix.
