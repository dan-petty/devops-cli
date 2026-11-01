# Proposal

## Why

A runner Job that stops an item sets the item back to Ready. A list of issues then shows an item that nobody tried (#2912). The stop comment names the cause, but the list does not. After a release fixes the cause, the runner image rolls. A person must notice the roll and comment `implement: retry`. On 2026-10-31 the stops of two items had a cause that the next release fixed, and the owner retried both by hand after the rollout.

The change makes a stop visible and lets a new runner image clear it:

- A stop sets `status/blocked`.
- The record keeps the digest of the runner image of the Job that stopped.
- A new digest in the CronJob template clears the stop one time. A second stop on the same digest waits for a person.

## What Changes

- A stop of the runner and a stop that the Service finds in a Job report set the Status `Blocked` through the one Status function (`derive_status`). The function gets the fact "a stop is on record".
- The Service records the digest of the runner image in `implement.job_digest` when it creates a Job. A report of the Job names the digest.
- The row `implement` gets two clear rules for an item that the Service set Blocked. Rule `retry`: a trusted person commented `implement: retry` after the stop comment. Rule `digest`: the digest in the template of CronJob `devops-cli-runner` differs from `implement.job_digest`. A clear removes `implement.stopped`, sets the Status back to Ready or Planned, and comments which rule ran.
- `ClusterJobs.template_digest` reads the digest from the CronJob template.
- The documents change: `docs/ROADMAP_WORKFLOW.md` (transitions, the Blocked row, the stop and retry path, the planned list) and step 16 of the Roadmap service in `k8s/README.md`.
- The change adds an observable behavior of the Service, so it carries spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: a stop sets Blocked, the digest is recorded, two clear rules.
- `roadmap-item-labels`: the Status function derives Blocked.
- `roadmap-item-claim`: the word of the claim rule follows the new stop Status.

## Impact

- Code: `src/devops_cli/roadmap/status_sync.py`, `implement_run.py`, `implement_submit.py`, `implement.py`, `store.py`, a new module `stop_clear.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/pull_status.py` (text only), and the message and help texts.
- Tests: `tests/roadmap/`, `tests/k8s/test_k8s_cluster_job_api.py`, `tests/invariants/test_roadmap_workflow_doc.py`.
- Documents: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`.

## Feasibility

The premise is that the digest of the failed Job is known, and that it can be compared with the digest of the CronJob template. I confirmed it against the real cluster with read-only `kubectl` and against the repository.

- The template of CronJob `devops-cli-runner` holds an image of the form `ghcr.io/dan-petty/devops-cli/runner:latest@sha256:<digest>`. Image Updater writes the digest there (`k8s/argocd/image-updater-values.yaml`, step "Service Image Updates" of `k8s/README.md`). The manifest in git names the image with no tag and no digest, and the cluster holds the digest.
- The image of every runner Job on the cluster has the same form as the template and holds the digest that the template had when the Job was made. The `imageID` of the pod of each Job is the same digest. So the digest of the template at the time of the create is the digest that ran.
- Decision: record the digest of the template when the Service creates the Job. The Job in the cluster and its pod are not a reliable source. The Job is deleted after one day (`ttlSecondsAfterFinished: 86400`), and a Job reported as `gone` has no object to read. A pod that never started (an image that cannot be pulled) has no `imageID`. The record in the issue body outlives all of these, and a person can read it.
- A Job that a person starts with `devops roadmap implement --item` or `devops k8s run-job` is not recorded by the Service. If such a Job stops an item, `implement.job_digest` is the digest of the last Job of the Service. The worst case is one extra clear for one digest, so the bound holds.
- The two reads of the CronJob (one for the digest, one in `create`) can differ when the image rolls between them. The record then holds the older digest. The worst case is again one extra clear.
- A template with no digest (for example a new Application before Image Updater writes it) gives no digest. A stop with no digest on record is never cleared by the digest rule. A person's retry still clears it.
- The code path exists today: `implement_submit._report` writes the stop of a Job that left its item eligible, `implement_run._ItemRun.stop` writes the stop of a step, and `sync_statuses` is the one Status writer. The label `status/blocked` exists in `.github/labels.yml` and `CONST_ROADMAP_STATUS_BLOCKED` is in the code.

## Existing Tool Considered

No open, maintained tool covers this need. Argo CD Image Updater (already in use) moves the digest, but it does not know a GitHub issue, a stop or a retry. Kubernetes `Job` `backoffLimit` retries a pod, not an item, and the runner sets `backoffLimit: 0` on purpose, because a Job that changed GitHub must never run twice. The comparison of two strings and the label write use the code that exists: the store, `derive_status`, `service_release` and `partition("@")` as `k8s/image_pins.py` does it.

Cost, as AGENTS.md rule 3 asks: about 150,000 tokens to build the change with its tests and documents, about 10,000 tokens a year to keep it, and about 1 hour of elapsed time. The change deletes the stop path that set `Ready` in `implement_run.py` and `implement_submit.py`, and the sentence in `docs/ROADMAP_WORKFLOW.md` that says a stop looks like Ready.
