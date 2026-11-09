# Proposal

## Why

A runner Job leaves two things in a poor form for the Service and for the next Job (#4071).

1. The Job does not say how its run ended. `_Ended` has the values `ready`, `stopped`, `yielded` and `returned`, but nothing writes it to the record. `_report` in `implement_submit.py` guesses from the Status of the item (`_settles_as_stop`). A run that a claim ended, or that a false premise returned, can look like a stop. A Job that was killed leaves no result, and then only its log gives a class.
2. A stop records the end of the failed check log (`implement.check_log`) and the unmerged files of a conflict (`implement.conflict`). Nothing reads them back. `_start` and `stop_clear.py` only set them to None. The first step of the next Job starts without the log that the stop recorded.

#4070 is merged, so the marks of a Job, its spend and its run comment are on `main`. This change adds the result as one more mark and uses the two stop records.

## What Changes

- Add `RESULT` (`implement.result`) to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py`. Its values are those of `_Ended`: `ready`, `stopped`, `yielded`, `returned`. Make that enum public next to the key, so that the runner and the Service use one definition.
- The runner writes `implement.result` as the last mark of each run, in the write that ends the run: `_ready` (`ready`), `stop` (`stopped`), `_return_to_new` (`returned`) and `yield_to` (`yielded`, a marks-only write). `_start` clears it in its first write, so a result of an earlier run never outlives the start of a new run. The Service clears it in the write that records a new Job (`_create`), so that a Job that dies before its first write does not leave a stale result.
- `_report` reads the result. A Job with the result `ready`, `yielded` or `returned` makes no stop, whatever the Status of the item. A Job with the result `stopped` keeps the class that the runner wrote in `implement.failure`. A Job with no result (killed, evicted or gone) uses the guess of `_settles_as_stop` and the log with `classify_failure`, as before. The pod exit status for the class `oom` stays with #3727.
- `_start` reads `implement.check_log` and `implement.conflict` before its first write, and gives both to the first step of the run. `run_step` gets a new optional input for them. The step message gets a new section `# The stop of the earlier Job`, and `roadmap_implement_step.md` states what the section holds. Only the first step of a run gets it.
- `_start` clears both keys in its first record write, for a retry of a person and for a continuation of the Service. `stop_clear.py` no longer clears them, so a Job that starts after a clear rule still finds them.
- The test of the record keys moves to `tests/roadmap/implement/test_roadmap_implement_record_readers.py`. `implement.result`, `implement.check_log` and `implement.conflict` get a reader in code. `GROUP`, `SHA` and `WIP` stay as a record for a person, with the spec line that requires each.
- Documents: the key table of `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`.
- Spec deltas for `roadmap-implement-job`: the requirements on the job record, on the report of a Job, on the failed check log and on the conflict stop are modified, and two requirements are new. The change is observable by a consumer (the record and the step input), so it carries deltas.
- The change adds one record key and no setting. The Settings models use `extra="ignore"`, and `decode_job_record` keeps only known keys and validates them as text or null. A record of an older version has no `implement.result` and loads as before (a test proves it).
- Request cost per Job: none added. The result rides on writes that exist. The Service clear rides on the write of `_create`.
- The change fits one pull request.
- Not in this change: the double count of the spend metric (#4200), the stage baseline (#4204) and the pod exit status (#3727).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job writes a typed result that the Service reads, and hands the check log and the conflict files of an earlier stop to the first step of the next run.

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_typed_result.py` (new), `tests/roadmap/implement/test_roadmap_implement_record_readers.py` (moved from `tests/invariants/test_roadmap_implement_record_keys.py` and extended), `tests/roadmap/test_roadmap_stop_clear.py`

## Feasibility

Checked on 2026-11-09 at origin/main 816cfe09. The blockers are merged: #3677 (pull request #4188) and #4070 (pull request #4202).

- No merged change, open pull request or newer issue does this work. The open pull requests are the release pull request and a placeholder plan summary. No branch for #4071 existed.
- Both faults exist as the issue states. `ImplementRecordKey` has no `RESULT`. `_Ended` (`implement_run.py`) is returned by `_implement_item` and counted in `ImplementApplied`, and written nowhere. `_settles_as_stop` and `_failure_of` in `implement_submit.py` guess from the Status and the log. `_start` sets `CHECK_LOG` and `CONFLICT` to None when `target.retry` is true and never reads them. `stop_clear.py` sets both to None in `_marks`. `run_step` and `build_step_inputs` take only a `FixRequest` for a log, and a fix step is not the first step of a retry.
- `_create` already writes `implement.job` and `implement.job_state` in one `service_claim` write, so the clear of a stale result adds no request.
- Old records: `decode_job_record` keeps only the members of `ImplementRecordKey` and checks each value as text or null, and `encode_job_record` keeps keys that another version wrote. A record with no `implement.result` loads with the key absent. `config/settings.py` sets `extra="ignore"` on its models, but the job record is not a Settings model, so only the record decoder matters.
- The new tests on origin/main: the cases of `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py` and the two amended cases of `tests/roadmap/test_roadmap_stop_clear.py` fail, each on its own assertion. The cases that guard a trap (a Job with no result keeps the class of its log, a stopped result keeps its class, a record of an older version loads) pass on the base. The run is cited in the pull request comment.
- A real GitHub remote and a real Service were not tested. The tests use a real git clone with a local `origin`, a scripted model, an in-memory store and a fake of the GitHub API and of the Kubernetes API.

## Existing Tool Considered

The item record marks (`set_marks`, `set_field`), `_Ended` and `implement.failure` (#3065) cover the need. They are existing code of the project. No open library marks the result of one job run in an issue record. No new library is needed. The change deletes the clear of `implement.check_log` and `implement.conflict` in `stop_clear.py` and the private name `_Ended`. Cost to build: about 80,000 tokens and 4 hours (one key, one reader, one hand-off input, the test of keys). Cost to keep: about 3,000 tokens each quarter. Cost to fix one miss: about 20,000 tokens and 1.5 hours.

## Dependencies

None. #3677 and #4070 are merged.
