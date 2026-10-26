# Tasks

## 1. Failing tests

- [x] Add failing `GitHubFake` test in `tests/test_roadmap_intake.py` verifying intake logs skipped fields and writes only the add when a person sets Priority during planning <!-- id: 0 -->
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py -k test_intake_skips_fields_when_person_adds_card_with_priority_during_planning`
- [x] Add failing `GitHubFake` test in `tests/test_roadmap_intake.py` verifying intake logs skipped Value, preserves person's milestone and Value, and writes Status, Effort, and Priority when a person sets Value and a milestone without Priority <!-- id: 1 -->
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py -k test_intake_skips_fields_when_person_sets_value_and_milestone_during_planning`

## 2. Implementation

- [x] Add `intake_skipped_fields` message string to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py` <!-- id: 2 -->
  - Verification: `uv run python -c "from devops_cli.lang.en.messages import MESSAGES; assert hasattr(MESSAGES.roadmap, 'intake_skipped_fields')"`
- [x] Update `_on_card` in `src/devops_cli/roadmap/intake.py` to log skipped fields and preserve person's milestone <!-- id: 3 -->
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`

## 3. Verification and checks

- [x] Verify `fail-to-pass` check run against base <!-- id: 4 -->
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify full CI checks pass <!-- id: 5 -->
  - Verification: `uv run devops ci`
- [x] Archive OpenSpec change <!-- id: 6 -->
  - Verification: `uv run devops openspec archive 1404-intake-log-skipped-card-fields`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
