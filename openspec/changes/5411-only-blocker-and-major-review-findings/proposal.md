# Proposal: #5411

## Why

Each open finding of the model review of a plan blocks the plan the same, whatever it costs. A minor finding keeps a plan at `plan/needs-fix`. Plan pull request #4917 (item #4472) kept the label for one `spec_delta_wrong` finding on the 7-file scenario. One line of the plan fixes it, and a test can still assert the other parts of that scenario. The eval of the reviewer gates only the recall, so nothing limits the findings that return a good plan.

Closes #5411.

## What Changes

- `Finding` gets a required `severity`: `blocker`, `major`, `minor` or `nit`, the `Severity` enum that the golden set uses (`stage_eval_cases.py`). The reply schema of a first review and of a later review requires it, so a reply with no severity goes back once.
- `open_findings` opens only a `blocker` or a `major` finding (`OPEN_SEVERITIES`). A `minor` or a `nit` finding is advice: the stage comment lists it with the points that stop no draft. The rule applies to the stage job, to the step `fix-plan` and to the review of refine, which use the same function.
- A later review (`judge_later`) opens a new finding only through `open_findings`, so the same rule applies to it. An earlier finding keeps its severity.
- The decisions of the step `fix-plan` count only open findings, so a head whose review finds only minor defects is `dismissed` and loses the label. The comment of a pushed revision, or of a plan that loses the label, lists the other findings of its reviews as advice, as the stage comment does.
- The comment line of a finding starts with its severity: ``- major `false_premise` at proposal (feasibility): ...``. The step `fix-plan` reads the severity back. A line of a comment from before this change has no severity, and it reads as a major finding, because each open finding of that release kept the draft.
- The prompt of the pass describes the four severities and says that only a `blocker` or a `major` finding can stop a plan. The `spec_delta_wrong` text says "has a scenario where no test can assert any part of its THEN", and a scenario with one part that no test can assert is minor. The prompt of the tools and of a later review name the severity too.
- `devops roadmap eval verify` states a ceiling of the findings that return a good plan, as a mean for each good plan that the run verified, next to the recall floor (`CONST_ROADMAP_VERIFY_GOOD_RETURNING_CEILING`). The JSON report holds the mean as `good_returning_mean`. A stored report from before this change has no severity, so `--resume` and `devops roadmap eval screen --reviewer` refuse it, as they refuse a report from before #5410.
- The change has a spec delta: the open rule, the comment line, the decisions of `fix-plan` and the report of the eval are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: a finding has a severity, and only a blocker or a major finding returns the plan and keeps it in draft.
- `roadmap-stage/fix-plan`: the decisions of the step count only blocker and major findings, and the comment lists the advice.
- `roadmap-refine/review`: only a blocker or a major finding refuses an item of a bot.
- `roadmap-stage-eval`: the verify report states the ceiling of the findings that return a good plan.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_later.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`, and each test that builds a finding.
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`, and the generated command reference.
- No manifest under `k8s/` changes.
- Release: the Service runs the stage job and the row `fix_plan` from its image, and a fix-plan Job runs the command from the same image. So the change needs a release and a roll of the image. After the release, the owner-approved step D9 sets `roadmap.fix_plan.mode` to `on`.

## Feasibility

- Source at `origin/main` 3f0d0f061 (0.129.1): `OPEN_TYPES` (`src/devops_cli/roadmap/stage/stage_verify.py:85-95`) has no severity, and `Finding` (`stage_verify.py:172-189`) has the fields `type`, `where`, `problem` and `quote` and no severity. `open_findings` (`stage_verify.py:602-620`) checks the place, the type and the quote. `judge_later` (`stage_verify.py:623-652`) opens a new finding only through `open_findings`. So one check in `open_findings` reaches the first review, the later review, the stage job, the step `fix-plan` (`PlanRevision.before`, `fixed`, `added` and `StagedChange.open_findings` all come from it) and the review of refine (`refine_judge.py:76`).
- The prompt line of `spec_delta_wrong` (`src/devops_cli/ai/tasks/roadmap_stage_verify.md:11`) says "has a scenario that no test can assert".
- The golden set grades each defect with `Severity` (`src/devops_cli/roadmap/stage/stage_eval_cases.py:112-118`): of 319 defects, 26 are blockers, 161 major, 100 minor and 32 nits. The minor and nit defects are of the kind that the issue names, such as a wrong reference in `feasibility`, a task that is not clear, or one part of a scenario that a test cannot assert. The eval gates only the recall of the blocker and major defects against `CONST_ROADMAP_VERIFY_RECALL_FLOOR` (`stage_verify_eval.py:370-381`), and it counts `good_returning` (`stage_verify_eval.py:162-165`) with no gate.
- `matched_defects` matches a finding to a labeled defect by type only, so the severity of a finding does not change the recall. Only the new prompt text can change what the model reports. The pull request runs the cases 2166 and 2169 with `deepseek-v4.1-flash-1017`, the model of `ai.tasks.verification` in the ConfigMap of the Service, on the base and on the head, one run at a time, and its comment gives both results.
- The step `fix-plan` reads the open findings back from the comment line (`_FINDING_LINE`, `src/devops_cli/roadmap/steps/fix_plan.py:189-193`). The open plan pull requests #5390 and #5422 hold stage comments in the form with no severity (read 2026-11-13), and the fixtures `tests/fixtures/roadmap_fix_plan/stage_comment*.txt` hold the same form. So the reader must read both forms, or the first attempts after the release lose the findings of those comments.
- The stored reports of `devops roadmap eval verify` with `deepseek-v4.1-flash-1017` of 2026-11-10 verified 5 good plans and give 14 findings that return a good plan, 2.8 for each good plan. The ceiling takes its value from the report of the head on the good plans.

## Existing Tool Considered

The `Severity` enum and the eval harness of the project (`stage_verify_eval.py`, pydantic-evals). No library grades a review finding. Cost to build: about 0.6 M tokens and 3 hours, with the eval runs. Keep: one field, one constant and one line form. Fix: about 0.1 M tokens for each wrong severity rule.
