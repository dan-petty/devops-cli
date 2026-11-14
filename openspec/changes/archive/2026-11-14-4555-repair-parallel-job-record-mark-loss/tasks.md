# Tasks

## 1. Behavior

- [x] 1.1 Define `RoadmapRecordMarkLostError` exception and telemetry instruments
  - Verification: `$ uv run pytest tests/roadmap/stores/test_roadmap_github_store_record_writes.py`
- [x] 1.2 Write failing tests for interleaved parallel writes, retry limit, and metric emission
  - Verification: `$ uv run pytest tests/roadmap/stores/test_roadmap_github_store_record_writes.py`
- [x] 1.3 Implement read-back verification, repair loop, and person edit restoration in `GitHubRoadmapStore`
  - Verification: `$ uv run pytest tests/roadmap/stores/test_roadmap_github_store_record_writes.py`
- [x] 1.4 Run full CI gates and verification checks
  - Verification: `$ uv run devops ci --only lint,format,typecheck,docs`

## 2. Documents

- [x] 2.1 Update documentation and validate openspec
  - Verification: `$ uv run devops ci docs`
