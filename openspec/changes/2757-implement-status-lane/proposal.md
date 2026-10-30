# Proposal

## Why

Issue #2757. The `implement` row waits behind the rows that call the model, though it calls no model in the Service pod. On 2026-10-30 the model lane of one repository started a round at 03:17:08. The round had not ended 31 minutes later, because the model answered about 3 requests in 35 minutes and the round was still in `refine`. The lane runs its rows in order: intake, refine, stage, implement, alternatives. A round that is still in `refine` never reaches `implement`. A person's comment `implement: retry` on #2656 made no Job for more than 90 minutes.

The row only talks to the Kubernetes API and to GitHub. The model runs in the runner Job. So the row has no reason to wait for the model.

## What Changes

- The row `implement` moves from `MODEL_LANE_ROWS` to `STATUS_LANE_ROWS` in `src/devops_cli/roadmap/run.py`. The status lane runs `metrics` and then `implement`, in the lane's own clone `clone`. A model-lane round that runs long no longer delays the row.
- Two lanes now write the issues of one repository at the same time: the model lane writes `refine.*`, `stage.*` and `alternatives.*` keys, and the status lane writes `implement.*` keys. The change proves that no write loses a key (see design). The store already holds one process-wide lock from the read of an issue to its `PATCH`, and GitHub has no conditional write of an issue. The change adds tests with two writers on one issue for the mixes that the move creates: a field write with refine marks against a mark write of the implement row, and a body write against a mark write. It adds no code to the store.
- The names of the rows of each lane change in `CONTEXT.md` (Lane), `k8s/README.md` (Roadmap service, step 16) and the docstrings of `run.py` and `constants.py`.
- The key of the ledger of failed rounds is the repository and the job name, with no lane. A record that an earlier version wrote loads as it is, and a suspended `implement` row stays suspended on the status lane. A test shows both.
- A consumer observes which lane runs the row (the label `lane` of `devops_cli_service_jobs_total` and of the other lane metrics), so the change carries spec deltas. It modifies one requirement of `roadmap-implement-job` and adds one requirement to it and one to `roadmap-item-labels`.
- The row keeps its interval of 10 minutes, its first-run rule and no batch key, no due rule and no cross-job rule. A trigger batch goes to both lanes as before, and a poll makes the row due by its interval.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-job`: the row `implement` runs on the status lane, after `metrics`, and a model-lane round that has not ended does not delay it.
- `roadmap-item-labels`: two writers of one issue keep each other's keys of the job record.

## Impact

- `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py` (comments).
- `tests/test_roadmap_run.py`, `tests/test_roadmap_implement_submit.py`, `tests/test_roadmap_github_store.py`.
- `CONTEXT.md`, `k8s/README.md`, and the documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The cause is in the code. `MODEL_LANE_ROWS` in `roadmap/run.py` lists `intake`, `refine`, `stage`, `implement`, `alternatives`, and `_execute_due_rows` runs a lane's rows one after the other. The adapter `_run_implement_adapter` calls `run_implement_round`, which calls `ClusterJobs` (the Kubernetes API) and the roadmap store (GitHub). It imports no model client and makes no model call.
- The Prometheus series of the Service on 2026-10-30 agree. For `dan-petty/devops-cli`, `devops_cli_service_jobs_total` shows 47 successes on the lane `status` and none on the lane `model`, which has 1 error. `devops_cli_github_requests_total` for the last two hours shows 82 requests of `refine` and 2 of `implement`.
- Lost update. `GitHubRoadmapStore.set_field`, `set_marks` and `write_issue_body` each read the issue and send one `PATCH` of its body inside `_JOB_RECORD_LOCK`, a process-wide lock. The Service runs both lanes as threads of one process, and `service_job` opens a store for each round, so every store of the Service takes the same lock. The `PATCH` carries the record block that was read inside the lock with only the written keys changed. The design has the proof.
- GitHub offers no conditional write of an issue. The page "Best practices for using the REST API" of docs.github.com says that conditional requests are for `GET` and that "Conditional requests for unsafe methods, such as `POST`, `PUT`, `PATCH`, and `DELETE` are not supported" unless an endpoint says otherwise. The page "Update an issue" lists the headers and parameters of `PATCH /repos/{owner}/{repo}/issues/{issue_number}`. It lists `accept` as its only header and no `If-Match`, `ETag` or `updated_at`. Both pages were read on 2026-10-30. So an `If-Match` write is not possible, and the lock plus the read before each write is the strongest guard that the API allows.
- The ledger. `FailureLedger` keys its entries by `(repo, job)` and `service-failures.json` is a list of `[repo, job, rounds, failed_on]`. No entry names a lane. The record that the current version wrote therefore loads with the new code, and the gauge `devops_cli_service_job_suspended` has the labels `repo` and `row`.

## Existing Tool Considered

The two-lane design of #1532 covers the need: it already gives each lane its worker, clone and round, and the store already holds the lock. For a conditional write, the GitHub REST API offers no tool (see Feasibility), and a lock library would add nothing to the one lock the store has. The change builds no code for this: it moves one row and adds tests. Cost, estimated: about 90 lines of tests and 20 lines of code, about 60k tokens of agent work and two hours of elapsed time.

The change deletes no code.
