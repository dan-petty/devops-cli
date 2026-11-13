# Proposal: #5410

## Why

A finding of the model review of a plan blocks the plan also when its place names no part of the plan. The place of a finding (`Finding.where`) is free text, and `open_findings` checks only the type and the quote. Plan pull request #5350 (item #5118, head ccfbab2e9586) kept `plan/needs-fix` for one finding on the requirement "A release writes through one Status writer". The spec delta of that head holds three other requirements. The quote came from the base spec `roadmap-item-labels`, which the reviewer read with the tool `read_spec`. So any plan can get a false blocker from a base spec that it does not change.

Closes #5410.

## What Changes

- `Finding.where` is a structured place (`Locator`): a `part` (`proposal`, `design`, `tasks`, `spec` or `issue`), a `section` (a key of the plan, a group number, a requirement name or a text of the issue), and the `capability` of a requirement.
- `VerificationInput.holds` checks the place against the plan of the request and the issue: a group number of `groups`, a requirement name of the spec delta of the capability, a key or a text of the proposal or the design, or a text of the issue. A tool answer holds no place.
- `open_findings` makes a finding open only when the plan or the issue holds its place. A finding on a part that the plan does not hold is advice, whatever its type and its quote. The rule applies to the stage job, to the step `fix-plan` and to the review of refine, which use the same function.
- A later review (#5409) applies the same rule to each new finding: `judge_later` opens a new finding only through `open_findings`, so a new finding on a place that the revision does not hold is advice, also with a quote in the changed text. An earlier finding that the later review marks `holds` keeps its locator and stays open, because the review that opened it checked its place.
- The check compares the words of a name, so a heading sign, a title after a group number, a scenario name or a cut requirement name keeps a place. A key of the proposal or of the design is a place of both parts. The part `issue` also reads the acceptance criteria of a proposal of refine. A capability is empty or a capability name, so the comment line reads back.
- The prompts `roadmap_stage_verify.md` and `roadmap_stage_verify_tools.md` describe the place. A `criterion_dropped` finding names the criterion of the issue (`part` `issue`), and a `missing_path` finding names the group that names or needs the file.
- The comment line of a finding shows the place as `<part> (<section>)`, with the capability of a requirement after the part (`stage_finding_where`, `stage_finding_where_capability`). The step `fix-plan` reads this form back from the last plan comment.
- `devops roadmap eval screen --reviewer` reads a stored report of `devops roadmap eval verify` with the same model as `--resume` (`stored_cases`). A report from before this change names the place of a finding as text, so both commands exit 1 with a message that names the file, and no pydantic error escapes.
- The change has a spec delta: the open rule and the comment line are observable behavior of the stage job, of `fix-plan` and of refine.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: a finding names a place that the plan or the issue holds, and only such a finding returns the plan.
- `roadmap-stage/ready`: only a finding whose place the plan or the issue holds keeps the plan in draft.
- `roadmap-refine/review`: only a finding whose place the proposal or the issue holds refuses the item.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/stage/stage_screen_eval.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`, `tests/commands/test_roadmap_eval_screen.py`, and the tests that build a finding. The fixtures `tests/fixtures/roadmap/plan_heads/5350-ccfbab2e9586/` and `tests/fixtures/roadmap_fix_plan/read_spec_5350.txt` hold the case of #5350. The finding lines of the stage comment fixtures use the new place form.
- Documents: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`.
- No manifest under `k8s/` changes.
- Release: the Service runs the stage job and the row `fix_plan` from its image, and a fix-plan Job runs the command from the same image. So the fix needs a release and a roll of the image.

## Feasibility

- Source at `origin/main` 2daf63a6c (0.128.0): `Finding.where` is `str = Field(min_length=1)` (`src/devops_cli/roadmap/stage/stage_verify.py:95`). `open_findings` (`stage_verify.py:298-313`) keeps a finding when its type is open and `given.contains(f.quote)`, or when it reports a placeholder that the request holds. No line reads `where`. `VerificationInput.contains` (`stage_verify.py:237-241`) also searches each tool answer.
- The plan of the request is `StageProposal.model_dump(mode="json")` (`_input_of` in `src/devops_cli/roadmap/stage/stage.py`). It holds `groups`, and `specs` with a `capability` and the names of `added`, `modified`, `renamed` and `removed` for each capability. So the step can check a place with no model call. The review of refine sends `RefinementProposal.model_dump` through the same `open_findings` (`src/devops_cli/roadmap/refine/refine_judge.py:69-76`).
- The case of #5350: `read_change` on the files of head ccfbab2e9586 gives one spec delta, `roadmap-item-claim`, with the requirements "A claim records the Status it replaces", "A release of an agent claim restores the Status" and "A release keeps a Status that a job did not set". The stage comment of #5118 (2026-11-13T03:40Z) lists the open finding "`spec_delta_wrong` at specs (A release writes through one Status writer)", with the quote "Every job and command that sets the Status of an item SHALL write it through `write_status` ...". That text is `openspec/specs/roadmap-item-labels/spec.md:216` at the merge base 869cb287fd05. `openspec show roadmap-item-labels --type spec --json` (openspec 1.17.0) at that commit gives the `read_spec` answer that the fixture holds.
- The real stage comments of the fixtures name places such as "specs (metric-instruments) and the rejected alternatives of group 2", "criteria (criterion 3) / group 4" and "group 2 (and the decision on service.instance.id)". No rule can read such free text as a part of the plan.
- The step `fix-plan` reads the open findings back from the comment line (`_FINDING_LINE` in `src/devops_cli/roadmap/steps/fix_plan.py`), so the reader changes with the line.
- The eval: `devops roadmap eval verify` matches each finding to a labeled defect by type only (`matched_defects` in `src/devops_cli/roadmap/stage/stage_verify_eval.py`), so the place rule does not change the recall. Only the new prompt text can change what the model reports. The reports that the command stored in its data directory show that the base does not reach `CONST_ROADMAP_VERIFY_RECALL_FLOOR` (0.9): 0.38 on 44 cases (2026-11-05) and 0.45 to 0.67 on runs of 9 and 10 cases (2026-11-10). The criterion "still meets the recall floor" thus has no base that meets it, and the issue now asks that the recall of the head on the same cases is not lower than the recall of the base. A run of the set is about 60 agent runs, and one case takes about 20 minutes with the model of the Service, so the pull request runs the cases 2166 and 2169 with `deepseek-v4.1-flash-1017` (the model of `ai.tasks.verification` in the ConfigMap of the Service), on the base and on the head, one model call at a time. The pull request comment gives both numbers.
- The eval of case 2166 on the first head of this pull request (2026-11-13) named `design` (`feasibility`) for the labeled `false_premise` blocker of `proposal.md`, with the first line of `feasibility` as the quote. With a set of keys for each file, `holds` made that blocker advice. The same run named places with the exact names in 20 of 21 findings, but `task 2.1`, `## Feasibility` or `Requirement: <name>` did not match. `RefinementProposal` holds its criteria in `acceptance_criteria` (`src/devops_cli/roadmap/refine/refine.py`), and the review of refine gets the body with no refine section (`refine_judge.py`), so a criterion of the proposal was in no text that the part `issue` read.

## Existing Tool Considered

A pydantic model with a `StrEnum` part, and the plan as the step already reads it (`StageProposal` as JSON). No library judges where a review finding points. #5215 adds a Jev check to fix-plan, but a decision model costs one call for each finding, and a check of the plan structure answers the question with no call. Cost to build: about 0.6 M tokens and 2.5 hours. Keep: one model, one check and one line form. Fix: about 0.1 M tokens for each wrong match rule.
