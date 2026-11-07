# Tasks

## 1. Refuse a security trigger without a security section

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_security.py` (new).

- [x] 1.1 Write `test_a_plan_that_changes_security_md_with_no_security_text_is_refused` in `tests/roadmap/stage/test_roadmap_stage_security.py`: a test builds the plan's own `StageProposal` with its security text and asserts that `content_problems` returns no problem for it, and a second test builds the same proposal with an empty `security` and asserts that the problem names `SECURITY.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py` fails on the base
- [x] 1.2 Add `SECURITY_TRIGGER_PATHS` as a documented tuple subclass and `SECURITY_TRIGGER_WORDS` to `src/devops_cli/roadmap/stage/stage_change.py`, add `security` to `StageProposal`, add the trigger match and the refusal to `content_problems`, and add the message `stage_problem_security` to `src/devops_cli/lang/en/messages.py`. The test also asserts that every trigger path exists and that a plan with no trigger gets no problem
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py` passes

## 2. Render the security section in the design file

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_security.py`.

- [x] 2.1 Write `test_the_design_file_holds_the_security_section` in `tests/roadmap/stage/test_roadmap_stage_security.py`: `render_change` of a proposal with security text writes a `## Security` section in `design.md`, and a proposal with an empty field writes none
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py` fails on the base
- [x] 2.2 Render the non-blank `security` text as a `## Security` section in `_design_file` of `src/devops_cli/roadmap/stage/stage_change.py`, after the rejected alternatives
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py` passes

## 3. State the security rule in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.

- [x] 3.1 Add the `security` key to the reply keys and a rule that names the trigger paths and words, the three questions and the `## Security` section of `design.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [x] 3.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` to state the security rule
  - Verification: `$ uv run devops ci docs` passes

## 4. Measure the stage job with the new rule

Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_change.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`.

- [x] 4.1 Add a golden case whose plan changes `SECURITY.md` with no security text and expects the security refusal, and run `uv run devops roadmap eval stage --replay` to record the score before and after the change. Fix any accepted case that the new rule now refuses by adding its security text
  - Verification: `$ uv run devops roadmap eval stage --replay` passes

## Criteria

- Group 1: A test shows that a plan that changes `SECURITY.md` and has no `## Security` part is refused, and that the same plan with the part passes.
- Group 1: A test shows that a plan with no trigger needs no part.
- Group 1: The trigger list is a named constant with a docstring, and a test fails when a path of the list does not exist.
- Group 3: The #3210 prompt-vs-rules test passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
