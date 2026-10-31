# Proposal

## Why

Issue #2035: `devops roadmap intake --source <issue>` does not link the candidate it files as a sub-issue.

When an agent splits an issue into parts, it files each part with `devops roadmap intake --source <link>`. The new issue has no sub-issue link to its parent on GitHub. A person or an agent links each part by hand. On 2026-10-23, an agent linked 14 split parts as sub-issues one at a time. This change links the filed issue to its parent automatically at file time.

## What Changes

- Add `add_sub_issue(parent, child)` to `RoadmapStore`, `GitHubRoadmapStore`, and `MemoryRoadmapStore`.
- `GitHubRoadmapStore` implements `add_sub_issue` with `POST /repos/{owner}/{repo}/issues/{parent}/sub_issues` and the REST database ID of the child.
- `MemoryRoadmapStore` records the sub-issue relationship and updates parent and child records.
- When intake files a candidate whose `--source` links an issue of the same repository, intake adds the candidate as a sub-issue of that issue.
- The dry-run plan lists the sub-issue write as a planned write.
- Update the docstring rule in `intake.py` to name the sub-issue link write as an allowed extra write.

## Capabilities

### Modified Capabilities

- `roadmap-intake-duplicates`: adds requirement to link candidates filed from `--source` as sub-issues.

## Impact

- Code: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/intake_requests.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/test_roadmap_store_contract.py`, `tests/test_roadmap_intake.py`, `tests/roadmap_github_fake.py`.
- Documentation: `docs/commands/roadmap.md` and `README.md` if options change.

## Feasibility

- GitHub REST API supports `POST /repos/{owner}/{repo}/issues/{issue_number}/sub_issues` with body `{"sub_issue_id": <id>}`.
- `POST /repos/{owner}/{repo}/issues` returns the issue with its REST ID (`id`).
- Verified against GitHub documentation and API schema on 2026-10-30.

## Existing Tool Considered

GitHub REST API provides the sub-issues endpoint `POST /repos/{owner}/{repo}/issues/{issue_number}/sub_issues`. It uses the existing GitHub REST API transport in `GitHubRoadmapStore`. No new library or external tool is needed.
