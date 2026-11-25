# Design

## Decisions
- Call `decode_job_record(held, issue=f"#{issue.number}")` inside `issue_from_event` (`src/devops_cli/roadmap/stores/brain_issues.py:79-93`) before instantiating `IssueRecord`, matching `GitHubRoadmapStore` REST record decoding (`src/devops_cli/roadmap/stores/github_store.py:252`).

## Rejected alternatives
- Coerce integer record fields inside `IssueRecord` or remove `int` encoding from `encode_job_record` (`src/devops_cli/roadmap/stores/store.py:1062-1076`): rejected because `encode_job_record` intentionally writes `implement.repair_rounds` as an integer (tested in `tests/roadmap/implement/test_roadmap_implement_records.py:78`), and `decode_job_record` (`store.py:1042-1059`) is the single parser that normalizes known keys, filters unknown keys from newer releases, and drops malformed non-string entries without crashing callers.
