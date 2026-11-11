# Proposal: #3670

## Why

#3670: each intake round of the Service reads the whole issue listing of the repository, `state=all`, because only `devops roadmap intake` reads through the listing snapshot of #4448. For this repository the listing is 47 pages (4,692 issues and pull requests). The scoped intake of each `issues` delivery and each intake round of the triage lane send all of them again. On 2026-11-11 the rows `intake` and `other` of the Service sent 28,317 GitHub requests in 24 hours, nearly all `GET` (12,000 answers of 200 and 16,000 answers of 304). In the last 2 hours, after #4522 moved the requests of the scoped intake to the row `intake`, the triage lane ran 78 rounds and sent 2,568 `GET` requests, about 33 a round.

The snapshot also keys to the version of devops-cli, so each release drops it. 117 releases came in 7 days.

## What Changes

- The intake rounds of the triage lane and the scoped intake of each delivery read every issue through `IncrementalListing` with `FileSnapshotStore` in `listing` of the Service's state directory, on its volume. A round with a kept snapshot reads only the issues changed since the watermark: one request when 100 or fewer changed.
- The triage lane runs its rounds and the scoped updates one at a time on its worker, so one writer keeps the snapshot of each repository. The status and model lanes keep the whole read.
- The snapshot keys to `LISTING_SCHEMA_KEY`, the first 16 hex characters of the sha256 of the JSON schema of `IssueRecord`, in place of the version of devops-cli. A release that keeps the record schema keeps the snapshot. A test pins the key.
- `intake_listing(state_dir, full=...)` builds the listing for the CLI, the triage lane and the scoped intake, so the three read the same file.
- The full read every 24 hours stays. The poll still reconciles each change that moved an `updated_at` (ADR 0017).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-listing`: the Service reads through the snapshot, and the snapshot keys to the record schema.

## Impact

- `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`
- `docs/roadmap/intake.md`, `k8s/README.md`
- A new file on the volume of the Service for each repository: 23.7 MB for this repository. Each intake round parses it (0.95 s) and writes it again (0.92 s), measured on a workstation for 4,692 records.
- A snapshot of an earlier version holds `version` and no `schema_key`. The first run after the update logs one warning that it cannot read the snapshot, reads the whole listing and writes a new snapshot.

## Feasibility

- Source at `origin/main` (a7668fec): `roadmap_consumer` opens the store of a scoped update with `get_roadmap_store(repo)` and no listing (`src/devops_cli/server/routes/webhooks.py`), and `service_job` does the same for each lane (`src/devops_cli/roadmap/run.py`). So `_every_issue` reads `state=all` in each round. Only `devops roadmap intake` passes `IncrementalListing`.
- The issue named `_execute_scoped` as the source of the row `other`. #4522 already gives the scoped intake the row `intake` (`request_scope(row=update.job)` in `run_scoped_update`). Prometheus shows the change: in the last 6 hours, `intake` 3,380 and `other` 1,497 requests.
- Prometheus, 2026-11-11, `sum by (row, status) (increase(devops_cli_github_requests_total{job="roadmap-service",row=~"other|intake"}[24h]))`: 28,317 requests; and `increase(devops_cli_service_jobs_total{lane="triage",result="success"}[2h])`: 78 rounds.
- The GitHub REST `since` parameter and the merge of the changed issues are in use since #4448; the tests of `tests/roadmap/stores/test_listing_snapshot.py` cover them.
- The Service's data directory is `/home/devops/.data` on the volume `roadmap-service-home` (`k8s/devops/roadmap-service/deployment.yaml`), so a restart keeps the snapshot.
- The issue proposed a cap of 10 pages for a scoped round. The plan replaces it: a cap hides changes after the last page, and intake compares each candidate with every item, so a partial listing gives wrong duplicate checks. The snapshot reads the changes and keeps a full listing.
- The new tests fail on the base: `intake_listing` and `LISTING_SCHEMA_KEY` do not exist, the lanes and the scoped update pass no listing, and a new package version drops the snapshot.

## Existing Tool Considered

- The REST `since` parameter and the `SnapshotStore` seam of #4448 cover the need. The change uses them and adds no library.
- gidgethub `cache=` and hishel: rejected in #4448. They keep no parsed record, and each new issue changes the ETag of each page of the default order.
- A cap on the pages of a scoped round, as the issue proposed: rejected, see Feasibility.
- Cost: about 80,000 tokens and 2 hours to build; about 5,000 tokens a month to keep and fix.
