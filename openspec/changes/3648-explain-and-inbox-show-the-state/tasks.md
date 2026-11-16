# Tasks

## 1. Record the action left with the stop

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/failure.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`.

- [ ] 1.1 `test_the_stop_comment_names_the_failure_class_the_action_taken_and_the_action_left` in `tests/roadmap/implement/test_roadmap_implement_job.py`, which delivers `The stop records the action left in the record` and its scenario `A stop with the action left amend`: beside its assertion on `implement.failure` it asserts that the record holds `implement.left_action` with `amend`; and `test_a_retry_clears_the_failure_class_with_the_stop` in the same module, which delivers the scenario `A retry comment on a stopped item`: it seeds `implement.stopped`, `implement.failure` and `implement.left_action` with `wait` in one `set_marks` call and asserts that the retry leaves none of the three keys, so the case fails before the retry path clears the new key
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py` fails on the base
- [ ] 1.2 Write the assertions first, and add `ImplementRecordKey.LEFT_ACTION: "wait"` to the `set_marks` call of the retry case. Add `LEFT_ACTION = "implement.left_action"` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py` and name it in the docstring of that class. In the marks of the stop in `src/devops_cli/roadmap/implement/implement_run.py`, add `ImplementRecordKey.LEFT_ACTION: left.value,` beside `ImplementRecordKey.FAILURE` at line 2016, where `left` comes from line 1983. In the retry branch of `_start` of the same module, add `marks[ImplementRecordKey.LEFT_ACTION] = None` beside `marks[ImplementRecordKey.STOPPED] = None` at line 795. Add the row of `implement.left_action` to the record key table of `docs/ROADMAP_WORKFLOW.md`, with the key in a code span. Add the entry `"implement.left_action": ("text", DOCUMENT, "The action left with the stop")` to `READERS` of `tests/roadmap/implement/test_roadmap_implement_record_readers.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_record_readers.py tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 1.3 Edit `docs/ROADMAP_WORKFLOW.md` to add the row of `implement.left_action` to the record key table, with the key in a code span and the words The action left with the stop
  - Verification: `$ uv run devops ci docs` passes

## 2. Remove the action left when a clear rule removes the stop

Kind: behavior. Reads: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/test_roadmap_stop_clear.py`. Changes: `src/devops_cli/roadmap/stop_clear.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

- [ ] 2.1 `test_a_clear_by_digest_removes_the_action_left_with_the_stop` in `tests/roadmap/test_roadmap_stop_clear.py`, which delivers the scenario `A clear by digest on a stopped item` of the requirement `A retry and a clear rule remove the action left with the stop`: a record that holds `implement.stopped` and `implement.left_action` loses both
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py` fails on the base
- [ ] 2.2 Write the case first, in the shape of the record that `tests/roadmap/test_roadmap_stop_clear.py` builds for a clear by digest. Add `ImplementRecordKey.LEFT_ACTION: None` to the marks of `_marks` in `src/devops_cli/roadmap/stop_clear.py`, beside `ImplementRecordKey.CHECK` at line 321, and say in the docstring of `_marks` that it removes the action left with the stop
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py` passes

## 3. Read the state of a stop and print it in explain

Kind: behavior. Reads: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/follow.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`. Changes: `src/devops_cli/roadmap/stop_state.py` (new), `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stop_state.py` (new), `tests/roadmap/test_roadmap_explain.py`.

- [ ] 3.1 `test_stop_state_reads_the_class_the_attempts_the_kept_work_and_the_action_left` in `tests/roadmap/test_roadmap_stop_state.py` and the extended `test_a_stopped_item_names_its_stop_for_the_implement_job` of `tests/roadmap/test_roadmap_explain.py`, which deliver the requirement `Explain names the state of a stopped item` and its two scenarios: an item whose record holds `implement.stopped`, `implement.failure`, `implement.left_action`, `implement.wip` and a trace of two attempts gives the class, the count of 2, group 2 with 3 of 5 tasks and `wait`, and a record with no class and no action left states both
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_state.py tests/roadmap/test_roadmap_explain.py` fails on the base
- [ ] 3.2 Write the two cases first. Add `src/devops_cli/roadmap/stop_state.py`: a frozen `StopState` that holds the step, the class text, the attempt count, the kept group and tasks and the action left, and `stop_state_of(item)` that returns None when the record holds no `implement.stopped`. It reads `ImplementRecordKey.FAILURE`, `ImplementRecordKey.LEFT_ACTION` and `ImplementRecordKey.WIP`, and counts the `TraceEventKind.ATTEMPT` events of the recorded step in the trace that `decode` of `src/devops_cli/roadmap/implement/implement_trace.py` reads, as `recorded_rows` of `src/devops_cli/roadmap/follow.py` counts them, so a step with no attempt event states no count. It counts no attempt when the value is no trace. It prints the class text that the record holds and looks up no table. Add the field `stop` to `Explanation` in `src/devops_cli/roadmap/explain.py`, fill it in `explain_item` on the open path from the item that the call reads already, and append its lines in `render_explanation` after the three job lines. Add the texts to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stop_state.py tests/roadmap/test_roadmap_explain.py` passes

## 4. Print the class, the attempts and the action left on the inbox line

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/stop_state.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`. Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`.

- [ ] 4.1 `test_a_stopped_item_shows_its_class_its_attempts_and_the_action_left` in `tests/roadmap/test_roadmap_inbox.py`, which updates `test_a_stopped_item_shows_its_step_and_is_cleared_by_the_retry_comment` and delivers the requirements `The inbox line names the class and the action left of a stop`, `The inbox line states the attempts of a stopped step` and `The inbox line of a stop with no class on record`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` fails on the base
- [ ] 4.2 Write the case first. In `_blocked_line` of `src/devops_cli/roadmap/inbox.py`, take the state from `stop_state_of(item)`: put the step and the class in the subject, put the attempt count there when it is above one, put the action left in the clear beside the retry comment, and state that the record holds no class when it holds none. Change the `stopped` subject and clear texts in `src/devops_cli/lang/en/messages.py` and keep the placeholders of the other lines
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes

## 5. Prove the inbox line of a stop sends no extra request

Kind: other. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/roadmap_github_store.py`, `tests/support/fakes/github_repository.py`, `tests/support/fakes/github.py`. Changes: `tests/roadmap/test_roadmap_inbox_requests.py`.

- [ ] 5.1 Write `test_the_inbox_sends_the_same_requests_for_a_stopped_item_as_for_an_item_with_no_stop` in `tests/roadmap/test_roadmap_inbox_requests.py`. It builds two repositories itself with `GitHubFake` of `tests/support/fakes/github_repository.py`, each with `GitHubFake(REPO, files={CONST_ROADMAP_LABELS_PATH: LABELS})`, one `seed_label` call for the label of that file, and one `seed_issue` call whose labels are `("priority/p2-medium", "status/blocked")` and whose `body` is `with_record("", encode_job_record({}, marks))`, because `select_items` of `src/devops_cli/roadmap/stores/store.py` keeps only an issue that holds a Priority and `open_items` of `src/devops_cli/roadmap/stores/github_store.py` builds the listing through it: the issue of the first holds the marks `implement.stopped`, `implement.failure` and `implement.left_action`, and the issue of the second holds no stop. It reads the inbox of each through `fake_store` of `tests/support/roadmap_github_store.py`, asserts that each inbox holds one `InboxKind.BLOCKED` line and that the line of the first names the class and the action left while the line of the second does not, then asserts that the GET paths in `github.calls` are equal and that no call reads one issue. The step also reads `tests/roadmap/test_roadmap_limit_classes.py`, the test whose `REGISTRY_COUNTS` entry declares the `CONST_ROADMAP_` prefix that the labels-file constant of the case belongs to, so the case keeps that constant covered
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_requests.py` passes

## 6. State the new output in the page and the help

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_command_help.py`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_command_help.py`.

- [ ] 6.1 State in the stop and retry section of `docs/ROADMAP_WORKFLOW.md` that `devops roadmap inbox` and `devops roadmap explain` print the class, the attempts, the kept work and the action left of a stop from the job record. In `src/devops_cli/lang/en/help.py`, rewrite the second sentence of the `inbox` help to name the class and the action left of a stopped item, so the help keeps three sentences, and add the stop state to the `explain` help. Update the help case in `tests/roadmap/test_roadmap_command_help.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_command_help.py tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 6.2 Edit `docs/ROADMAP_WORKFLOW.md`, the help of `devops roadmap inbox` and `devops roadmap explain` in `src/devops_cli/lang/en/help.py`, and the help case in `tests/roadmap/test_roadmap_command_help.py`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 7. Regenerate the command reference

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`. Changes: `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`.

- [ ] 7.1 Run `uv run devops docs generate` and commit its output in `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md`, which now state the new output of `devops roadmap inbox` and `devops roadmap explain`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 7.2 Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A test: `explain` for a stopped item prints the class, the attempts, the kept work and the next action.
- Group 4: A test: `inbox` prints the class and the next action on the line of a stopped item, and the attempts when there is more than one.
- Group 5: A test: `inbox` makes no more GitHub requests than before.
- Group 2: A test: a retry or a clear rule removes the new record value with the stop.
- Group 4: A stop with no class on record, from an earlier image, still prints its line.
- Group 6: `docs/ROADMAP_WORKFLOW.md` and the command help state the new output.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
