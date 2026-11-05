# Proposal

## Why

Issue #3479: the hardening audit `.github/workflows/defect-pr-hardening-audit.yml` files an issue for each merged defect pull request that adds no line to a declared hardening surface. A regression test and a living spec do not count, so the audit reports a tested fix as unhardened. It filed 8 issues in three days (#3138, #3313, #3345, #3383, #3402, #3455, #3459 and #3469). Each issue has the same text, with no root cause and no lesson, so no person and no job can plan from it. Each one also uses an intake round.

The audit also goes against the document that owns the rule. `docs/SELF_IMPROVEMENT.md` (Continuous self-hardening) says that a check that fails when the problem returns guards a defect, and that a rule goes into a document only when no check is possible. A test under `tests/` and a requirement under `openspec/specs/` are such checks. The issue text of the workflow cites `AGENTS.md`, which holds no such rule.

## What Changes

- `CONST_HARDENING_SURFACES` in `src/devops_cli/config/constants.py` gets two entries: `tests/` and `openspec/specs/`. `match_hardening_surface` in `src/devops_cli/github/defect_classifier.py` matches an added path under each of them, so `audit_pr_hardening` counts a regression test and a living spec as a guardrail. An addition under `openspec/changes/` still counts for nothing.
- `.github/workflows/defect-pr-hardening-audit.yml` appends the report of `devops pr hardening-report` to `$GITHUB_STEP_SUMMARY` and exits 0 for an unhardened pull request. The workflow does not pass `--fail-on-missing`, files no issue and holds no `issues: write` permission. Its text cites `docs/SELF_IMPROVEMENT.md` and no longer cites `AGENTS.md`.
- A recorded file list of pull request 3467 (`tests/fixtures/github/pull_request_3467_view.json`) lets a test audit the real case offline.
- `tests/github/test_defect_classifier.py` and `tests/invariants/test_workflow_contracts.py` hold the new rules. The old rules of both files change with the code: a `tests/` line no longer leaves a pull request unhardened, and the contract of the workflow no longer asks for the issue step or for `--fail-on-missing`.
- The command `devops pr hardening-report`, its options (`--fail-on-missing` stays) and its messages do not change, so no generated document changes.
- The change carries a spec delta for the new capability `pr-hardening-audit`, because the report of a command and the contract of a workflow are observable.
- The change fits one pull request.

## Feasibility

- `uv run devops pr hardening-report --pr 3467` on the base prints `Missing` and `PR #3467 failed hardening audit: no additions on declared hardening surfaces`. The recorded file list of that pull request (`gh pr view 3467 --json files`, as `_fetch_pr_view_payload` reads it) holds 186 added lines under `tests/` and 64 under `openspec/specs/`, so the premise holds.
- A script ran `audit_pr_hardening` on `main` for the 8 pull requests of the family (#3137, #3310, #3342, #3381, #3399, #3442, #3452 and #3467). Each one is reported as not hardened, and each one adds between 34 and 496 lines under `tests/` and between 5 and 64 lines under `openspec/specs/`.
- The same script counted the lines under `openspec/changes/`: each of the 8 pull requests adds between 2 and 176 lines there, because each one writes its change folder. So the folder cannot count as a guardrail: every pull request would pass.
- `audit_pr_hardening` in `src/devops_cli/github/defect_classifier.py` sums the additions of a file only when `match_hardening_surface` names a surface, and `CONST_HARDENING_SURFACES` seeds the count of each surface. Two entries and two prefix tests are the whole code change.
- `docs/SELF_IMPROVEMENT.md` lines 165 to 168 hold the rule that the workflow must follow. A search of `AGENTS.md` and `CONTRIBUTING.md` for `hardening` finds no rule that a defect fix writes a line to a declared document.
- `_audit_single_pr` in `src/devops_cli/commands/pr.py` exits 0 for an unhardened pull request unless `--fail-on-missing` is set, so the workflow step needs no change of the command to write a summary and exit 0.
- No open pull request changes the classifier, the workflow or their tests, and issue #1979 (which moved the lesson from `AGENTS.md` to the document that owns it) is closed.

## Existing Tool Considered

The GitHub job summary (`$GITHUB_STEP_SUMMARY`) and the existing command `devops pr hardening-report` cover the need. The job summary shows a report to a person without a gate and without an issue. It cannot block a merge, and a post-merge audit cannot block one either. The change adds no new tool, no dependency and no home-grown code beyond two path prefixes.

The change deletes these internal parts: the step "Hand unhardened defect finding to intake" of the workflow with its inline issue text and its list of surfaces, the `issues: write` permission, the `--fail-on-missing` argument of the workflow step, the `AGENTS.md` citation, the assertions of `assert_audit_workflow_contract` that require them, and the cross-check of `test_match_hardening_surface_declared_surfaces` between the surface list of the workflow and the constant.

## Capabilities

### New Capabilities

- `pr-hardening-audit`: A test and a living spec count as a hardening guardrail, a defect pull request with no guardrail is reported as not hardened, and the audit workflow writes a job summary and files no issue.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/github/defect_classifier.py`
- Workflow: `.github/workflows/defect-pr-hardening-audit.yml`
- Tests: `tests/github/test_defect_classifier.py`, `tests/invariants/test_workflow_contracts.py`, `tests/fixtures/github/pull_request_3467_view.json` (new)
