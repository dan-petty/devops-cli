# Tasks

## 1. The job ticks a group whose exit checks pass

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_failure_class.py`, `tests/roadmap/test_roadmap_implement_step_attempts.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_step_ticks.py`, add the test that a group whose verification and static checks pass, with no tick from the model, ends done, and that its commit holds the group ticked
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_ticks.py`
- [x] 1.2 In `tests/roadmap/test_roadmap_implement_step_ticks.py`, add the test that a group with no `Verification:` line and passing exit checks ends done with its tasks ticked in the commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_ticks.py`
- [x] 1.3 In `tests/roadmap/test_roadmap_implement_step_failure_class.py`, remove the test that a task left unticked stops the step with `not_ticked`, and in `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`, `tests/roadmap/test_roadmap_implement_step_attempts.py` and `tests/roadmap/test_roadmap_implement_step_repair.py` rewrite the tests that expect the tick turn to the job-owned ticks
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_failure_class.py tests/roadmap/test_roadmap_implement_step_attempts.py tests/roadmap/test_roadmap_implement_step_repair.py`
- [x] 1.4 In `src/devops_cli/roadmap/implement_step.py`, tick the unticked tasks of the own group after the hooks pass, stage `tasks.md`, and delete the unticked guard, the tick turn and their messages in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_ticks.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_step_failure_class.py tests/roadmap/test_roadmap_implement_step_attempts.py tests/roadmap/test_roadmap_implement_step_repair.py`

## 2. The fix step and the staged strays

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_strays.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_strays.py`, `tests/roadmap/test_roadmap_implement_strays.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_implement_strays.py`, add the tests that a fix step deletes a new file outside `src/`, `tests/`, `docs/` and `openspec/`, that a staged stray is unstaged and deleted in a group step and in a fix step, and that a new test file under `tests/` stays in a fix step
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_strays.py`
- [x] 2.2 In `src/devops_cli/roadmap/implement_step.py` and `src/devops_cli/roadmap/implement_strays.py`, list the staged new files with the untracked files, remove the fix-step early return of `_strays`, and unstage each stray with `git rm --cached --force --ignore-unmatch` before the deletion
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_strays.py tests/roadmap/test_roadmap_implement_step.py`

## 3. The prompt and the extra turn for a tick

Kind: behavior. Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_implement_prompt.py`, add the test that the prompt holds no promise of an extra turn for a missing tick and says that the job ticks a group whose checks pass
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py`
- [x] 3.2 In `src/devops_cli/ai/tasks/roadmap_implement_step.md`, replace the sentence of the extra turn for a missing tick with the sentence that the job ticks a group whose exit checks pass
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py`

## 4. Tell the reader

Kind: other. Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `openspec/config.yaml`, `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 4.1 In `openspec/config.yaml`, state the plan rule for a group with no verification command: the job ticks the group when its exit checks pass
  - Verification: `uv run devops openspec check`
- [x] 4.2 In `docs/roadmap/implement.md` and `docs/ROADMAP_WORKFLOW.md`, state that the job ticks a passing group, that a missing tick gets no extra turn, and that the stray files of a fix step and of a staged file are removed, then regenerate the documents with `devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`
- [x] 4.3 Confirm that no document or source file still names the extra turn for the ticks
  - Verification: `! git grep -n -F "extra turn for the ticks" docs src`

## 5. The tests of the stop for an unticked task, and the class not_ticked

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/failure.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_implement_wip.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_step_hooks.py`, `tests/roadmap/test_roadmap_implement_step_own_text.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/prometheus/test_implement_failure_labels.py`.

- [x] 5.1 In `tests/roadmap/test_roadmap_implement_wip.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_step_hooks.py` and `tests/roadmap/test_roadmap_implement_step_own_text.py`, rewrite the tests that expect a stop for a task the model did not tick, so that they stop for a failed check or a failed model call, or end done with the job's ticks
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_wip.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_step_hooks.py tests/roadmap/test_roadmap_implement_step_own_text.py`
- [x] 5.2 In `tests/roadmap/test_roadmap_failure.py` and `tests/prometheus/test_implement_failure_labels.py`, remove the class `not_ticked` from the lists of the classes and of the actions
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/prometheus/test_implement_failure_labels.py`
- [x] 5.3 In `src/devops_cli/roadmap/failure.py`, remove the class `not_ticked` and its default action, and in `docs/ROADMAP_WORKFLOW.md` remove its row from the table of the classes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/prometheus/test_implement_failure_labels.py`

## Workflow follow-up

- The test-form check of #3451 keeps a task unticked. That stop needs a class of its own, because this change removes `not_ticked`. The criterion waits for #3451, which is absent from `origin/main`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
