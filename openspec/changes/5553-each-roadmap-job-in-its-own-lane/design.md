# Design

## Decisions

### D1. One lane for each row, by default

`service_lanes(groups)` in `src/devops_cli/roadmap/run.py` makes the table of lanes from `DEFAULT_DUE_TABLE`. With no groups, each row is a lane of its own, and the name of the lane is the name of the row. Each named group of `service.lanes` is one lane that holds the rows it names. The rows of a lane run in the order of the table, so `stage` stays before `refine` in a lane that holds both (#4796). The lanes come in the order of their first row. `service_jobs` makes one job for each lane, and `ServiceManager` makes one `RepoWorker` for each lane and repository, as before. A lane is a worker thread and its trigger queue, so a lane never waits for another lane.

`ServiceConfig.lanes` checks the form of the setting: each lane name and each row name is a lowercase name (`[a-z][a-z0-9_]*`), each lane names at least one row, and no row is in two lanes. `service_lanes` checks the names against the table: an unknown row, or a lane name that is the name of a row in another lane, raises `ConfigurationError` with the field `service.lanes`. `devops serve --service` builds the lanes before it starts, so a wrong setting stops the start with the error. The Service reads the setting only when it starts.

### D2. A clone for each lane that needs files

The rows `metrics`, `implement`, `stage`, `fix_plan`, `refine` and `alternatives` need files. Each lane that holds one of them works in its own clone, `<data dir>/roadmap/<owner>/<name>/lanes/<lane>`, which `ensure_checkout` makes and updates with its contract unchanged. `service_job` gives `run_due_jobs` the clone directory of its lane. Two lanes have two names, so they have two directories.

Measured on 2026-11-13 for devops-cli (git 2.47.3 in the image, 2.55.0 on the workstation):

| Form for 6 lanes | Disk | Isolation |
| --- | --- | --- |
| One clone and a `git worktree` for each lane | 152 MB + 6 x 101 MB = 758 MB | The lanes share `refs/remotes/origin/*` |
| A blobless clone for each lane | 6 x 129 MB = 774 MB | Full; a read of an older file fetches it from GitHub |
| A clone for each lane | 6 x 152 MB = 912 MB | Full |

A worktree saves 154 MB, but the lanes share their refs. Two worktrees of one clone fetched 40 times each while the remote moved 300 branches 20 times. 4 of 80 fetches failed with `cannot lock ref 'refs/remotes/origin/main': is at <a> but expected <b>`. With `core.filesRefLockTimeout` and `core.packedRefsTimeout` at 30000, 6 of 80 failed: the error is a compare-and-swap of the ref, not a held lock. The rows fetch inside their rounds (`stage` before its push, `fix_plan`, `branch_authors` in `clone_git.py`, `add_worktree`), so a lock in the checkout cannot hold them, and a lock around each of those fetches touches the stage and implement code that #4559 and #5411 change now. A clone for each lane has its own refs and needs no lock.

### D3. The Service removes the state of the lanes it does not run

When `devops serve --service` starts, `retire_lane_state` removes, in each repository directory of `service.repos`, each clone under `lanes/` whose lane the Service does not run, and the clones of the three earlier lanes, `clone`, `model-clone` and `triage-clone`. In the state directory, it removes each `listing-<name>` whose lane the Service does not run. The clones and the snapshots are caches: a lane clones again and reads the whole listing once. A path that it cannot remove goes to the log as a warning, and the start goes on.

### D4. A listing snapshot for each lane

Each lane reads every issue through `lane_listing(state_dir, lane)`, the snapshot `listing-<lane>` of the state directory, and its worker is the one writer of each file (#4854). The lane that holds `intake` reads through `intake_listing(state_dir)`, the snapshot `listing`. The scoped intake of a delivery reads the same snapshot and runs on the same worker, so that snapshot also has one writer (#3670). The rows of the earlier model lane read the whole listing in each round: 49 pages for devops-cli. Through a snapshot, a round reads one page of changes, and the whole listing once in 24 hours.

A lane that no row of which reads the listing, such as `github_status`, writes no snapshot: `IncrementalListing` writes only when a store reads through it.

### D5. Scoped updates and the trigger subject

`ScopedUpdate` names its row and no lane. The webhook consumer runs the scoped update on the lane that holds the row (`lane_of_row(row, service.lanes)`). When the update wakes other rows (`scoped_update_wakes_lanes`: an edit, or a placement of a critical fix or a P0 item), the consumer sends the trigger to each other lane of the repository. A lane whose rows the trigger does not make due runs a round that sends no request. The consumer sends no trigger to the lane of the update, so the intake row does not run a whole round for the same delivery.

`RepoWorker.enqueue` and `ServiceManager.enqueue_trigger` take an optional `subject`, the number of the issue of the event. The worker keeps the subjects of the triggers that a batch coalesces in `TriggerBatch.subjects`. This is the seam for #5555, which routes events to lanes by subject. No row reads the subjects yet.

### D6. Shared limits and item safety

Each limit of the pod stays shared by every lane: the model call semaphore (`model_call_slot`, `service.model_call_concurrency`), the GitHub budget (`RequestBudget`, `service.github_requests_per_hour`), the round pause and halt, and one `FailureLedger` for all lanes. `schedule.json` and `queues.json` keep `_SCHEDULE_LOCK`. The budget sets the poll interval from the mean cost of a round (`RequestBudget.poll_interval`), so more lanes with cheaper rounds keep the requests of a poll.

Lanes that touch the same issue:

| Field | Rows that write it | What keeps it safe |
| --- | --- | --- |
| Status | `intake` (New), `refine` (Ready), `stage` (Planned), `implement` (In Progress, stop clear) | Each row writes only from the states that it takes; a write of a Status that changed since the read raises `RoadmapItemChangedError` (`head_moved`) |
| Body blocks and the job record | `intake`, `refine`, `alternatives`, `stage`, `implement` | `_JOB_RECORD_LOCK` of the GitHub store holds each write from its read to its `PATCH` in the process |
| Title | `retitle` | One writer; `stage` reads the title |
| Plan pull request and branch | `stage` (opens, removes), `fix_plan` (pushes), `stage_ready` (marks ready), `pr_conflicts` (comments) | Pushes with a lease; a moved head fails the push (`head_moved`) |

New overlaps that the one model lane hid: `retitle` can change a title while `stage` plans the item, so a plan can take the earlier title; the next `retitle` round of a Planned item takes the title of its plan pull request. `refine` can change the design of a Ready item while `stage` plans it, so the plan reads the earlier design. Both were possible before between two rounds.

### D7. Telemetry

The span of each round and of each scoped update has `service.lane` (`RepoWorker`). `devops_cli_service_jobs_total` has the label `lane`. `devops_cli_roadmap_row_seconds` gets the attribute `lane` in a round that has a lane; a round of the command line has none. The default lane of a row has the name of the row, so the histogram keeps its series count.

### D8. Memory, disk and threads

Memory, measured on 2026-11-13: 744 MiB now, and the largest working set of one pod in the last 3 days is 1459 MiB, against a limit of 3 GiB and a request of 768 MiB. A round that reads the devops-cli snapshot parses 27 MB of JSON: 90 MiB for the first copy in a process and 45 MiB for each other copy. At the first poll of a pod, up to 11 lanes of devops-cli read their snapshot at the same time, which adds about 0.6 GiB for the length of the parse. The expected peak is about 2.1 GiB, below the limit, so the manifest keeps its limits. The live check after the release reads the largest working set of the first day (task 4.1).

Disk, measured on 2026-11-13: 588 MB used on a claim of 1 GiB. With the default lanes: the devops-cli clones take about 0.9 GB (D2), the clones of the 6 other repositories about 0.24 GB, and the snapshots up to 11 x 28 MB, about 0.3 GB, so about 1.45 GB. The class `local-path` keeps a volume in a directory of the node, does not hold it to its size and cannot grow a claim in place (`k8s/README.md`). A change of the claim size is refused for a bound claim of this class, so the manifest keeps 1 GiB.

Threads: 14 lanes for each of 7 repositories make 98 worker threads in place of 21. Each waits on a condition with a 0.2 s timeout.

### D9. Overlap with the stage Job (#4559 part 2)

The branch `feat/4559-run-each-stage-item-in-its-own-job` moves the row `stage` from `MODEL_LANE_ROWS` to `STATUS_LANE_ROWS` and changes `_run_stage_adapter`, `model_clone` and the module docstring of `run.py`. This change keeps `_run_stage_adapter`, `model_clone` and the three row tuples. It changes the module docstring and `service_jobs`. With one lane for each row, the move of `stage` changes only the order of `DEFAULT_DUE_TABLE`. #5411 changes the review gate of `stage.py`, not the lanes.

The specs that name the status lane or the model lane for the order of rows (`roadmap-retitle`, `roadmap-stage/round`, `roadmap-stage/fix-plan`, `roadmap-stage/ready`, `roadmap-pr-conflicts`) mean the row groups `STATUS_LANE_ROWS` and `MODEL_LANE_ROWS` of the table, which keep their names. #4559 part 2 changes two of those specs, so this change leaves them; the follow-up that renames the row groups also changes their wording.

## Rejected alternatives

- **One clone and a `git worktree` for each lane**: rejected by the fetch test of D2. Concurrent fetches into the shared `refs/remotes/origin/*` fail by compare-and-swap, also with the git lock timeouts, and the rows fetch inside their rounds.
- **A blobless clone for each lane**: rejected. It saves 23 MB for each devops-cli lane, and a read of a file on another branch or in older history fetches it from GitHub in the round.
- **`git clone --reference` or `--shared` to one object store**: rejected. The git documentation says that a repository that borrows objects loses them when the reference repository prunes them.
- **One snapshot that all lanes share behind a lock**: rejected. Each lane then waits for the listing read of the other lanes, and #4854 keeps one writer for each snapshot file.
- **The whole listing for the earlier model rows**: rejected. Each lane of those rows would read 49 pages of devops-cli in each round, which is the cost of the budget stop of #4854.
- **A new queue library (Celery, RQ, Dramatiq, arq)**: rejected. Each needs a broker process, and the Service already has a worker and a queue for each lane. ADR 0021 moves the jobs to cluster units later.
- **A larger claim**: rejected. A bound `local-path` claim cannot grow, and the class does not hold a volume to its size.
