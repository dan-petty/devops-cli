# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the status and triage lanes open their stores with their own snapshots; a second status round with a kept snapshot sends one listing request with `since`; a later stop pass lists no comments of a stop whose issue did not change, and lists them again after a comment
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_stop_clear.py`
- [x] 1.2 Add `lane_listing` and give it to the status lane; add `retry_asked_on` and use it in the stop pass and the implement judge
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/stores/test_listing_snapshot.py`

## 2. Documents

- [x] 2.1 Update the files of the Service volume and the cost of a stop in `k8s/README.md`, and the lanes in `docs/roadmap/intake.md`
  - Verification: `$ uv run devops ci docs`
