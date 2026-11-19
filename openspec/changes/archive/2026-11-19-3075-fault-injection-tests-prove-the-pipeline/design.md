# Design

## Decisions

- **Use one parametrized table in `tests/roadmap/test_roadmap_faults.py`, keyed by `FailureClass`, for the stage and implement cases.**: The project runs pytest already, and one table shows every case and lets the coverage gate compare the table with the enum.
- **Drive each stage and implement case through the real job with `JobWorld.run` on the edge fakes and a scripted model.**: The class, the action, the final label and the comment are written by the stop path, so a case that stops short of it proves nothing about recovery.
- **Make the coverage gate read `{case.klass for case in FAULT_CASES} == set(FailureClass)` and name each missing class.**: `tests/roadmap/test_roadmap_failure.py` reads `ACTION_BY_CLASS` the same way, so a new class fails the suite without a case.
- **Make the halt record unwritable by putting a regular file where its parent directory would be, not a directory at the record's path.**: `src/devops_cli/server/service.py:343` starts the Service halted when the record exists, and `_halt` then writes nothing. With a file as the parent, the record does not exist at construction, so `_halt` reaches `keep_state_record` and its write fails.
- **State the measured duration of the three fault modules in the module docstring and hold it under 60 seconds in a `process` step, and assert no elapsed bound in a test.**: `docs/TESTING.md:141` forbids an upper bound on wall-clock time, and the ast-grep rule `test-elapsed-upper-bound` fails a test that adds one, so the bound is a measurement a person repeats.
- **Keep every wait on the `clock` fixture and every edge on an in-memory fake.**: The hermetic floor fails a test that reaches a real edge, and the clock fixture records each wait, so the suite adds no real time.
- **Split the Service lane cases into a state-file module and a row module.**: Each step then reads a small set of files that fits the budget, and each module mirrors the module that it drives.
- **Assert the failed marks write through the stage failure record and the item's job record, not through a comment.**: `write_each` catches the `GitHubOperationError` as a plain `DevOpsCLIError` and `_write_failure` records its class and masked message, and the staged comment is never posted because it comes after the marks write.
- **Keep the intake-apply case in the row module even though `tests/roadmap/intake/test_roadmap_intake_github_requests.py` already asserts the class and the person's label.**: The existing test posts no comment and asserts no kept record, and the fault table needs the case for the count and for the Service lane matrix.

## Rejected alternatives

- **A custom fault harness beside pytest.**: The project already runs pytest and requires the Tests & Coverage check, so a second runner adds maintenance and no coverage.
- **Recorded provider responses replayed over HTTP.**: `docs/adr/0007-tests-double-only-process-edges.md` doubles only process edges, and the hermetic floor refuses a real network edge.
- **A hand-kept checklist that every class has a case.**: The checklist drifts from the code; `tests/roadmap/test_roadmap_failure.py:494` shows that comparing the enum with a table fails on a new class.
- **A per-test assert on elapsed time, or a 60-second assert on the suite.**: `docs/TESTING.md:141` holds `No test bounds elapsed wall-clock time from above.` and the rule `test-elapsed-upper-bound` in `.ast-grep/rules/` fails such an assert.
- **Live cluster and model calls for the killed pod and the OOM.**: The issue requires offline cases, and the exit status of the job's pod carries the killed pod and the OOM as 143 and 137.
- **Make the halt record unwritable with a directory at the record's path, as the earlier plan did.**: `src/devops_cli/server/service.py:343` holds `self._halted = halt_record is not None and halt_record.exists()`, so the Service starts halted and `_halt` never calls `keep_state_record`.
- **Assert that the stop comment names the write that failed after the draft pull request exists.**: `src/devops_cli/roadmap/stage/stage.py:1946` holds `def _write_failure(item: Item, exc: DevOpsCLIError) -> StageFailure:`, so the record names the error class and its masked message and the comment is never posted.
