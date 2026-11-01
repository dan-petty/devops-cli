# Tasks

## 1. Add retry_days config and failure record structure

Reads: none. Changes: `src/devops_cli/roadmap/alternatives.py`.

- [ ] 1.1 Write a test that asserts the config key roadmap.alternatives.retry_days exists with a default of 3, and that the failure record dataclass holds item_number, error_class, and failed_at, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k retry_days` fails on the base
- [ ] 1.2 Add the retry_days key to the alternatives config section with a default of 3. Define a dataclass AlternativeFailure with fields item_number (int), error_class (str), and failed_at (datetime). Add a helper that reads the failure record from the item's job record and one that writes it, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k retry_days` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Per-item error isolation in the alternatives round

Reads: none. Changes: `src/devops_cli/roadmap/alternatives.py`.

- [ ] 2.1 Write a test with five items where one item's check raises UnexpectedModelBehavior. Assert the round returns success, four items have their checks written, and the failing item's job record holds the error class and the time, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k partial_failure` fails on the base
- [ ] 2.2 Wrap each item's check call in a try/except block. On exception, build an AlternativeFailure record with the item number, the exception class name, and the current time. Write the record to the item's job record. Format the stop reason using bounded_text from the #2875 pattern and the readable provider text from #2922. Continue to the next item. After the loop, return success if at least one item was checked, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k partial_failure` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Retry delay for failed items

Reads: none. Changes: `src/devops_cli/roadmap/alternatives.py`.

- [ ] 3.1 Write a test where an item failed 1 day ago and retry_days is 3. Assert the item is skipped. Write a second test where the item failed 4 days ago. Assert the item is checked again, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k retry_delay` fails on the base
- [ ] 3.2 Before checking an item, read its AlternativeFailure record from the job record. If the record exists and the elapsed time since failed_at is less than retry_days, skip the item and do not count it toward the round's limit. If the elapsed time is at or past retry_days, clear the failure record and proceed with the check, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k retry_delay` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Row fails only when zero items are checked

Reads: none. Changes: `src/devops_cli/roadmap/rows.py`.

- [ ] 4.1 Write a test where all five items fail. Assert the row returns a failure and the failure counts toward the 3-round suspension. Write a second test where one item fails and four succeed. Assert the row returns success and no suspension count is added, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k total_failure` fails on the base
- [ ] 4.2 Track the count of items that were successfully checked in the round. After the loop, if the count is zero, raise the row failure error that triggers the suspension counter. If the count is greater than zero, return success. The existing suspension logic in the row scheduler is unchanged; it still counts three consecutive failures, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k total_failure` passes
- [ ] 4.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. Update documentation for the new behavior

Reads: none. Changes: `k8s/README.md`, `docs/TELEMETRY.md`.

- [ ] 5.1 Write a test that reads k8s/README.md and asserts the alternatives row section states that a failed item is recorded and the round succeeds, and that the row fails only when no item could be checked, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k docs` fails on the base
- [ ] 5.2 In k8s/README.md line 610, replace the sentence 'If the check of an item fails, the row writes the other checks and fails, naming the item.' with the new behavior: a failed item is recorded in its job record with the error class and time, the round succeeds, and the item is retried after roadmap.alternatives.retry_days. In docs/TELEMETRY.md line 83, add a note that a failed check is recorded in the job record and does not count in the metric, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py -k docs` passes
- [ ] 5.3 k8s/README.md, docs/TELEMETRY.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
