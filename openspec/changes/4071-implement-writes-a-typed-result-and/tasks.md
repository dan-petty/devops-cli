# Tasks

## 1. The Job writes how its run ended and the Service reads it

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/support/roadmap_implement.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_typed_result.py` (new), `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`.

- [x] 1.1 Write the failing tests `tests/roadmap/implement/test_roadmap_implement_typed_result.py` (typed_result, no_result, handoff and an old-format record)
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py` fails on the base
- [ ] 1.2 Add `RESULT` to `ImplementRecordKey` and to its docstring in `src/devops_cli/roadmap/stores/store.py`, and make `_Ended` a public enum next to it for the runner and the Service
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py -k "old_format"`
- [ ] 1.3 In `src/devops_cli/roadmap/implement/implement_run.py`, write `implement.result` as the last mark of `_ready`, `stop` and `_return_to_new`, write it in a marks-only write in `yield_to`, and clear it in the first write of `_start`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py -k "typed_result or no_result"`
- [ ] 1.4 In `src/devops_cli/roadmap/implement/implement_submit.py`, clear `implement.result` in the write of `_create`, and read it in `_report` so that `ready`, `yielded` and `returned` make no stop
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. The first step of a run gets the stop of the earlier Job

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Changes: `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/test_roadmap_stop_clear.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/lang/en/messages.py`.

- [x] 2.1 Write the failing tests of the hand-off in `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, and amend the two cases of `tests/roadmap/test_roadmap_stop_clear.py` that expect a clear of `implement.check_log` and `implement.conflict`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py tests/roadmap/test_roadmap_stop_clear.py` fails on the base
- [ ] 2.2 Give `run_step` and `build_step_inputs` in `src/devops_cli/roadmap/implement/implement_step.py` an optional input for the check log and the conflict files, with the section `# The stop of the earlier Job` in the message, and describe the section in `src/devops_cli/ai/tasks/roadmap_implement_step.md`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py -k "handoff"`
- [ ] 2.3 In `_start` of `src/devops_cli/roadmap/implement/implement_run.py`, read both keys before the first write, pass them to the first step of the run only, and clear both in the first write for every start
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_typed_result.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_job_scoped.py`
- [ ] 2.4 Remove the clear of `implement.check_log` and `implement.conflict` from `_marks` in `src/devops_cli/roadmap/stop_clear.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py`

## 3. Every record key has a reader

Kind: other. Reads: `tests/invariants/test_roadmap_implement_record_keys.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_record_readers.py` (moved and extended), `tests/invariants/test_roadmap_implement_record_keys.py` (moved away).

- [x] 3.1 Move the test of the keys to `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, add `implement.result` with its reader in `implement_submit.py`, and name a reader in `implement_run.py` for `implement.check_log` and `implement.conflict`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_record_readers.py` fails on the base
- [ ] 3.2 Check that the keys, the readers and the spec lines agree after groups 1 and 2
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py`

## 4. State the result and the hand-off in the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [ ] 4.1 In `docs/ROADMAP_WORKFLOW.md`, add the row of `implement.result` to the table of the record keys, and change the rows of `implement.check_log` and `implement.conflict` to say that the next Job reads them, hands them to its first step and clears them
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`
- [ ] 4.2 In `docs/roadmap/implement.md`, state that a Job writes its result last, that the Service reads it, and that the first step of a run gets the stop of the earlier Job
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The runner SHALL write `implement.result` as the last mark of a run that is ready, stopped, yielded or returned, and SHALL clear it in its first write.
- Group 1: The Service SHALL clear the result when it records a new Job, SHALL cause no stop for a Job with the result `ready`, `yielded` or `returned`, and SHALL take the class of a Job with no result from its log.
- Group 1: A record of an older version SHALL load with no `implement.result`.
- Group 2: The first step of a run SHALL get the check log and the conflict files of the earlier stop, and no later step SHALL.
- Group 2: A clear rule of the Service SHALL keep both keys, and the next Job SHALL clear them in its first record write.
- Group 3: Each member of `ImplementRecordKey` SHALL have a reader in code or a line of the spec or the document, and a member with neither SHALL fail the test.
- Group 4: The documents SHALL name `implement.result`, the hand-off and the new clear point.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
