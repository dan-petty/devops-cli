# Tasks

## 1. The verification module

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_stage_verify.py` for the scenarios of "A finding has one of the nine defect types" and for the input of the pass: the cited files and their caps, the payload, the quote rule, the problem for the planner and the findings section
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py`
- [x] 1.2 Write `src/devops_cli/roadmap/stage_verify.py` (`Finding`, `Verification`, `VerificationInput`, `verify`, `returning`, `return_problem`, `findings_section`), the prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, the three `CONST_ROADMAP_STAGE_VERIFY_*` constants and the messages of a finding
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py`

## 2. The pass in the stage job

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_stage_verification.py` for the scenarios of "A verification pass follows the gates", "An evidence-backed finding returns the plan once" and "Other findings go into the comment", with a faked model edge for the planner and another for the verifier
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py`
- [x] 2.2 Add the `verifier` to `plan_stage` and to the planner of `stage.py`, keep the plan and the findings on `StagedChange`, list the findings in the comment, and pass `get_llm_client(task="verification")` from `devops roadmap stage` and from the stage adapter of the Service; answer the verification request in the tests of the command and of the round that use the model fake
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py tests/roadmap/test_roadmap_stage_job.py tests/roadmap/test_roadmap_stage_command.py tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_apply.py`

## 3. The eval command

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_stage_verify_eval.py` for the scenarios of "The verify command scores the verification pass", "The verify command fails on a failed call and has a dry run" and "The group lists the verify command"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py`
- [x] 3.2 Write `src/devops_cli/roadmap/stage_verify_eval.py` and `src/devops_cli/commands/roadmap_eval_verify.py`, register `verify` in `roadmap_eval.py`, and add the help and the messages of the command
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py tests/roadmap/test_roadmap_stage_eval_command.py`

## 4. The documents and the archive

- [x] 4.1 Regenerate the command documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`
- [x] 4.2 Archive the change
  - Verification: `uv run devops openspec archive 3153-the-stage-job-verifies-its-plan`

## Workflow follow-up

- Pending a person: set `ai.tasks.verification.model` to `claude-sonnet-5-5` in `config.yaml`, run `devops roadmap eval verify` and record the score in a comment on the issue.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
