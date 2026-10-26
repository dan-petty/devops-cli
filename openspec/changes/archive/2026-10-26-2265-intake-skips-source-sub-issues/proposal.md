# Proposal

## Why

Issue #2265: intake names another sub-issue of the candidate's source issue as a possible duplicate.

An agent splits an issue into parts. It files each part with `devops roadmap intake --source <link to the issue>`, then links the part to the issue as a sub-issue. Each part changes a different set of commands, so the titles differ only in the command group. Intake keeps the source issue out of the duplicate check, but it still compares a new part with the parts that are already sub-issues of that source. On 2026-10-25, intake named a sibling as a possible duplicate for 4 of 22 parts of #886. Each flag asks a person to close one of two issues that are both needed.

## What Changes

- `IssueRecord` carries `parent`: the number of the issue of the same repository that has the issue as a sub-issue. The GitHub store reads it from `parent_issue_url` in the issue listing, so intake sends no new request.
- When the source of a new candidate links an issue of the repository, intake leaves that issue and every sub-issue of it out of the duplicate comparison.
- The help text of `--source` and the module documentation of intake say so.
- This change alters observable behavior of `devops roadmap intake` (the issues the model sees and the possible duplicate it names), so it carries a spec delta.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-duplicates`: adds a requirement that a part is not compared with the other sub-issues of its source.

## Impact

- Code: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/test_roadmap_intake.py`, `tests/roadmap_board_fake.py`, `src/devops_cli/roadmap/memory_store.py` (the in-memory store seeds `parent`).
- Documentation: `docs/commands/roadmap.md` and `README.md`, regenerated.

## Feasibility

- Premise confirmed on 2026-10-26 against the GitHub REST API with `devops gh api`.
- `GET repos/{repo}/issues?state=all` returns `parent_issue_url` on each issue of the listing. Issue #2240 returns `https://api.github.com/repos/dan-petty/devops-cli/issues/886`, and issue #2265 returns `null`.
- Issue #886 returns `sub_issues_summary.total` of 23.
- `src/devops_cli/roadmap/intake.py` `_Planner._decide` keeps out of the shortlist only the candidate and the issue its source links (`_source_issue`). No code reads the sub-issues of that issue.
- Every issue payload also returns `repository_url`. A parent in another repository starts with a different `repository_url`, so the store can tell it from a parent in this repository with no request.

## Existing Tool Considered

The `parent_issue_url` field of GitHub's own issue listing names the parent of a sub-issue. It covers the need and adds no request and no dependency. The alternative, `GET repos/{repo}/issues/{n}/sub_issues`, needs one more request for each source.

The change deletes no internal code. It adds one field to `IssueRecord` and one set to the existing exclusion in `_Planner._decide`.
