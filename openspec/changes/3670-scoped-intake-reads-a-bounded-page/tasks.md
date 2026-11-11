# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the scoped intake with a kept snapshot sends one listing request; only the triage lane opens its store with the snapshot of the state directory; the scoped update of a delivery does too; a new package version with the same record schema keeps the snapshot; the pin of the schema key
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/test_roadmap_run_scoped_update.py tests/roadmap/test_roadmap_run_lanes.py tests/server/test_server_service.py`
- [x] 1.2 Key the snapshot to the schema of `IssueRecord`, add `intake_listing`, and give it to the triage lane and the scoped update
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/test_roadmap_run_scoped_update.py tests/roadmap/test_roadmap_run_lanes.py tests/server/test_server_service.py tests/roadmap/intake/test_roadmap_intake_dry_run.py`

## 2. Documents

- [x] 2.1 Update the issue listing section of `docs/roadmap/intake.md`, the files of the Service volume in `k8s/README.md` and the dry-run condition text
  - Verification: `$ uv run devops ci docs`
