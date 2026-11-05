# Tasks

## 1. Count a test and a living spec as hardening surfaces

Reads: `src/devops_cli/github/defect_classifier.py`, `src/devops_cli/config/constants.py`, `tests/github/test_defect_classifier.py`. Changes: `src/devops_cli/github/defect_classifier.py`, `src/devops_cli/config/constants.py`, `tests/github/test_defect_classifier.py`, `tests/fixtures/github/pull_request_3467_view.json` (new).

- [x] 1.1 In `tests/github/test_defect_classifier.py`, write first: a defect pull request with additions under `tests/` is hardened and names `tests/`; one with additions under `openspec/specs/` is hardened and names `openspec/specs/`; one with additions under `src/` only is not hardened and names no surface; one with additions under `openspec/changes/` and `src/` only is not hardened; the recorded file list of pull request 3467 (`tests/fixtures/github/pull_request_3467_view.json`) is hardened through `tests/` and `openspec/specs/`. Change the two older tests that hold a `tests/` line as unhardened or that read the surface list of the workflow
  - Verification: `uv run devops ci test tests/github/test_defect_classifier.py` fails on the base
- [x] 1.2 Add `tests/` and `openspec/specs/` to `CONST_HARDENING_SURFACES`. Make `match_hardening_surface` read the constant with `PurePosixPath.full_match` and delete its if-chain, and name both surfaces in the docstring of `defect_classifier.py`
  - Verification: `uv run devops ci test tests/github/test_defect_classifier.py tests/commands/test_pr_hardening_report.py` passes

## 2. Report to the job summary and file no issue

Reads: `.github/workflows/defect-pr-hardening-audit.yml`, `docs/SELF_IMPROVEMENT.md`, `tests/invariants/test_workflow_contracts.py`. Changes: `.github/workflows/defect-pr-hardening-audit.yml`, `tests/invariants/test_workflow_contracts.py`.

- [x] 2.1 In `assert_audit_workflow_contract` and its mutation test, require that the report step writes to `$GITHUB_STEP_SUMMARY` and does not pass `--fail-on-missing`, that no step creates an issue or runs `devops roadmap intake`, that `permissions` holds `contents: read` and `pull-requests: read` and no `issues` entry, and that the text of the workflow cites `docs/SELF_IMPROVEMENT.md` and not `AGENTS.md`
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py` fails on the base
- [x] 2.2 In `.github/workflows/defect-pr-hardening-audit.yml`, delete the step that hands the finding to intake and the `issues: write` permission, make the report step append its output to `$GITHUB_STEP_SUMMARY` and keep the exit status of the command, drop `--fail-on-missing`, and add a comment at the head that cites `docs/SELF_IMPROVEMENT.md`
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py` passes

## Criteria

- A defect pull request with additions under `tests/` is hardened.: group 1
- A defect pull request with additions under `openspec/specs/` is hardened.: group 1
- A defect pull request with no test, no spec and no surface line is not hardened.: group 1
- `devops pr hardening-report --pr 3467` reports pull request 3467 as hardened.: group 1
- A pull request that is not hardened appears in the job summary of the workflow.: group 2
- The workflow has no step that creates an issue, and it does not pass `--fail-on-missing`.: group 2
- The workflow text does not cite `AGENTS.md`, and it agrees with `docs/SELF_IMPROVEMENT.md`.: group 2

## Workflow follow-up

- The 8 family issues (#3138, #3313, #3345, #3383, #3402, #3455, #3459 and #3469) end as not planned, each with the reason in a comment, and a comment on #2526 and on #2660 states the decision on its scenario. These are GitHub writes that no offline test checks. Follow-up: #3661.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
