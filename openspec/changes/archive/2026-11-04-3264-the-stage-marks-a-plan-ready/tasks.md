# Tasks

## 1. Classify the findings of the verification pass

Reads: `src/devops_cli/roadmap/stage_verify.py`, `tests/roadmap/test_roadmap_stage_verify.py`. Changes: `src/devops_cli/roadmap/stage_verify.py`, `tests/roadmap/test_roadmap_stage_verify.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_verify.py`, assert that a finding whose quote is in the input and whose type is `missing_path`, `false_premise`, `ignores_existing_code`, `spec_delta_wrong` or reports a placeholder is open, and that a finding with no quote in the input or an unlisted type is not open
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` fails on the base
- [x] 1.2 Add `open_findings(findings, given)` to `src/devops_cli/roadmap/stage_verify.py`: it returns the findings that have a quote in the input and match the open defect types, and it reuses the quote check of `returning`. Give the label name one constant `PLAN_NEEDS_FIX_LABEL` in the same module
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` passes

## 2. Keep a plan with an open finding in draft

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/stage_github.py`, `tests/roadmap/test_roadmap_stage_verification.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_verification.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_verification.py`, with a fake client that returns a placeholder finding, assert that the staged change carries the open findings, that `_stage_one` applies `plan/needs-fix`, and that `_notes` puts the findings first; and assert that a client that returns no open finding applies no label
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py` fails on the base
- [x] 2.2 Carry the open findings on `StagedChange` beside `findings`. In `_stage_one`, apply `plan/needs-fix` to the created pull request when the open findings are not empty, and remove it when they are empty. In `_notes`, render the findings section before the plan-run report
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py` passes

## 3. Refuse to mark a plan with an open finding ready

Reads: `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/github/client.py`, `tests/roadmap/test_roadmap_run.py`. Changes: `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/github/client.py`, `tests/roadmap/test_roadmap_run.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_run.py`, assert that the row makes no mark and posts a comment that names `plan/needs-fix` when the pull request holds the label, and that it marks the pull request when the label is absent
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py` fails on the base
- [x] 3.2 In `src/devops_cli/github/client.py`, add `labels` to `PullStatus`. In the decision function of the `stage_ready` row, read the labels of the pull request with the checks and return the refusal with a comment that names the label when `plan/needs-fix` is present. Keep the single function that decides and the single function that marks
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py` passes

## 4. Count a plan with an open finding as plan_defect

Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_failure.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_failure.py`, assert that the classifier maps an open finding of the stage to the class `plan_defect`, and that an item with an open finding is not counted as staged
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py` fails on the base
- [x] 4.2 Map an open finding of the stage to the existing class `plan_defect` in the classifier of `src/devops_cli/roadmap/failure.py`, and report the item of a plan with an open finding as a failed attempt in `stage_results` of `src/devops_cli/roadmap/stage.py` so the round counts no staged plan
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py` passes

## 5. Record the #3174 case in the golden set

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`. Changes: `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/case.json` (new), `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/facts.json` (new), `tests/roadmap/test_roadmap_stage_eval_run.py`.

- [x] 5.1 Write the case folder from the plan of #3174: its issue text, its recorded plan with the single group titled `placeholder`, the tracked files that the gates need, and a `case.json` whose defect has the type `other` and the gate `none`, because no replay gate judges the open-finding stop. Extend the replay test so the report lists the case and its placeholder group
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_run.py` passes

## 6. Document the open-finding stop

Reads: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 6.1 State in `docs/roadmap/stage.md` that an open finding keeps the plan in draft with `plan/needs-fix` and the findings first in the comment, and that the row `stage_ready` refuses that pull request. State in `docs/ROADMAP_WORKFLOW.md` that such a plan counts as a failed attempt of class `plan_defect`
  - Verification: `uv run devops ci docs` passes
- [x] 6.2 Update `docs/roadmap/stage.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 2: A test with a fake client that returns a placeholder finding shows that the plan pull request is opened as a draft with the label and the findings in the comment.
- Group 2: A test shows that a plan with no finding is staged as today.
- Group 3: A test shows that the ready row refuses a plan with an open finding, and states why.
- Group 5: The golden-set replay includes #3194 or #3174 as a case.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
