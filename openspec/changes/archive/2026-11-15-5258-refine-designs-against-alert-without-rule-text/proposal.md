# Proposal: #5258

## Why
When an issue names a code-scanning alert, refine previously read only the rule identifier from the issue body. The scanner rule description was not retrieved. Without the rule description, refine generated proposals that addressed the wrong scanner rule, and the judge approved them. Closes #5258.

## What Changes
- Add `rule_description` to `CodeScanningAlert` in `src/devops_cli/security/alert_filer.py`.
- Add `read_alert(session, repo, number)` to retrieve alert metadata with one GET request.
- Add `alert_number_of(text)` to extract code-scanning alert numbers from text.
- Update `refine_one_item` in `src/devops_cli/roadmap/refine/refine.py` to retrieve named alerts, add alert details to request context and allowed URLs, and include rule requirements in key questions.
- Update `judge` in `src/devops_cli/roadmap/refine/refine_judge.py` to compare proposals against alert rule descriptions and refuse mismatched proposals.

## Capabilities
- Refine includes scanner rule descriptions in design evidence and verification input when items cite code-scanning alerts.
- Refine judge refuses proposals that contradict alert rule requirements.

## Impact
- Items for code-scanning alerts generate designs that match the reported scanner rule.
- Scanner alerts are not closed with incorrect fixes.

## Feasibility
- Verified with code-scanning alert 213 in repository `dan-petty/devops-cli`.
- GitHub REST API endpoint `/repos/{repo}/code-scanning/alerts/{number}` provides `rule.description`.

## Existing Tool Considered
- The GitHub REST API code-scanning endpoint is used directly through `GitHubSession`. No new external dependency is needed.
