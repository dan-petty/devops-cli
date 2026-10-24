# Task: Intake Never Judges a Split Part a Duplicate of the Issue That Its Source Names (#1985)

**Issue**: [#1985](https://github.com/dan-petty/devops-cli/issues/1985)
**Scope**: scope/roadmap
**Feasibility**: Confirmed against the code at origin/main (6d978fff): `_Planner._shortlist` in `src/devops_cli/roadmap/intake.py` left out only the candidate itself, and only `NewCandidate.filed_body` read the source. Confirmed against GitHub with read-only requests on 2026-10-24. The seven issues split on 2026-10-23 (#772, #596, #1113, #1387, #1391, #1533, #1876) each have a "Tracking issue" section and sub-issues. The three originals into which a person closed a duplicate (#452, #1418, #1014) have no sub-issues. The five originals of the 2026-10-20 folds that #1755 records also have none. The filed parts of #772 (#1978, #1982, #1983, #1984) end with `Source:` and the GitHub link of #772. The REST issue listing that intake reads gives each issue `sub_issues_summary.total`. ADR 0012 says that a person splits an issue too large for one pull request into sub-issues.

## Description

An agent files each part of a split issue with `devops roadmap intake --source <link of the issue>`. Intake judged some parts duplicates of that issue and filed nothing, so the part had no issue for a pull request to close. Two rules now come from GitHub's data, not from the model or from the text:

- A new candidate is not compared with the issue that its source links. That issue is the one whose GitHub link is the source without its query and fragment. Thus a link to a comment of the issue names the issue too.
- An issue that has sub-issues is compared with no candidate. Its sub-issues deliver it, one pull request each, so no candidate asks for its change. A parent that a run places does not join the comparison set. Thus a newer sub-issue in the same run is not closed as its duplicate.
- `IssueRecord.sub_issues` holds the count of sub-issues that GitHub records. The GitHub store reads it from the issue listing, with no other request.
- The intake prompt has no change. Since #1755, it says that an umbrella item and the candidate that it contains are not duplicates. The folds of 2026-10-23 ran before #1755 merged.
- CONTEXT.md defines a **Duplicate** with the two rules. The help of `devops roadmap intake` and of `--source` states them.

## Acceptance Criteria

- [x] Tests first: a new candidate whose source names an issue of the repository is never judged a duplicate of that issue. This is also true when the model names that issue with a shared change. The test runs over the in-memory store and the shared model fake. It uses a link to the issue and a link to a comment on it (`test_a_part_is_never_a_duplicate_of_the_issue_its_source_names`).
- [x] A new candidate that repeats another item, not its source, is still a duplicate (`test_a_part_that_repeats_an_item_other_than_its_source_is_still_a_duplicate`).
- [x] An issue that has sub-issues is never the original of a candidate (`test_an_issue_with_sub_issues_is_never_the_original_of_a_candidate`, `test_a_sub_issue_decided_after_its_parent_in_one_run_is_not_closed_as_its_duplicate`, and `test_an_item_whose_issue_github_lists_with_sub_issues_is_on_no_shortlist` over the GitHub fake).
- [x] The tests run offline.
- Pending a person: write the body of #2026 to a file. Run `devops roadmap intake --title "fix(valkey): valkey.url keeps its scheme, so a valkeys url dials tls with host name checks" --body-file <file> --source https://github.com/dan-petty/devops-cli/issues/1113 --plan`. The report shows no `duplicate of #1113` line.

## Deliverables

- [x] `IssueRecord.sub_issues`, which the GitHub store reads from `sub_issues_summary.total` and the in-memory store seeds (`src/devops_cli/roadmap/store.py`, `github_store.py`, `memory_store.py`).
- [x] Intake leaves the issue that the source links and every issue that has sub-issues off the shortlist (`src/devops_cli/roadmap/intake.py`).
- [x] The help of `devops roadmap intake` and `--source`, and the generated documents.
- [x] The CONTEXT.md entry **Duplicate**.
- Intake adds a filed part as a sub-issue of the issue that its source names: moved to #2035.
