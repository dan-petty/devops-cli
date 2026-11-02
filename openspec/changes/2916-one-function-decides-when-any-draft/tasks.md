# Tasks

## 1. Add the readiness function and its table test

Reads: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/github/check_verdict.py`. Changes: `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_readiness.py` (new).

- [ ] 1.1 tests/roadmap/test_roadmap_readiness.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_readiness.py` fails on the base
- [ ] 1.2 Add ReadinessKind, ReadinessStatus and Readiness to src/devops_cli/roadmap/implement_pull.py, and draft_readiness(pull, kind, item, extra_checks=()) which reads the tick state of the change's tasks and the archive state for kind IMPLEMENT and returns ready, wait, or refuse with a reason. Write the failing table test first over the four kinds with complete and incomplete rows, and verify that `uv run devops ci test tests/roadmap/test_roadmap_readiness.py` passes

## 2. Route the stage row through draft_readiness

Reads: `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_stage_ready.py`. Changes: `src/devops_cli/roadmap/stage_ready.py`, `tests/roadmap/test_roadmap_stage_ready.py`.

- [ ] 2.1 tests/roadmap/test_roadmap_stage_ready.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_ready.py` fails on the base
- [ ] 2.2 Make ready_to_mark call draft_readiness with kind STAGE_PLAN and the recorded item, so the row keeps its behavior and the one function decides. Update the test doubles in tests/roadmap/test_roadmap_stage_ready.py to the new call, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_ready.py` passes

## 3. Route the implement job through draft_readiness

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 3.1 tests/roadmap/test_roadmap_implement_job.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [ ] 3.2 Make the implement job call draft_readiness with kind IMPLEMENT before mark_ready at implement_run.py:683, and leave the pull request a draft with the reason when the answer is refuse. Add the failing test for a partial pull request first, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 4. Block check-readiness on a refused implement pull request

Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr.py`.

- [ ] 4.1 tests/commands/test_pr.py, and verify that `uv run devops ci test tests/commands/test_pr.py` fails on the base
- [ ] 4.2 Add the draft_readiness refusal to assess_merge_readiness as one blocker that names the unticked group, with its text in src/devops_cli/lang/en/messages.py, and let check_readiness render it through the existing blocker path. Write the failing command test first, and verify that `uv run devops ci test tests/commands/test_pr.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
