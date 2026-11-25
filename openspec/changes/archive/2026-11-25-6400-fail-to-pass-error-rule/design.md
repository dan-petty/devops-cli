# Design

## Decisions
- **Match file-level collection errors against all head cases of the module**: In `_repaired_and_refused`, when `test_id` has no `::` and `pb` is a module-level error (`not pb.classname` and `pb.status in _NOT_PASSED`), select head cases whose `classname` equals `test_id` or starts with `f"{test_id}."` (or whose `classname == ""` and `name == test_id`, in case head still fails collection). Mark repaired only when that set is non-empty and every case has `status == "passed"`. Record the repaired outcome under the module `test_id` (`pb.model_copy(update={"status": "passed", "message": ""})`) so `FailToPassReport.proof` continues to exclude the unchanged file's base collection error.
- **Expose `TestCaseOutcome.error_phase` via one prefix map**: Map `CONST_FAIL_TO_PASS_PROOF_ERROR_MESSAGES` to `"collection"` and `"setup"` and `"failed on teardown with"` to `"teardown"` so `TestCaseOutcome.error_phase` returns the phase for errored outcomes and `proves_fix` reuses that map cleanly.
- **Verify real pytest output under `@pytest.mark.live("python")`**: Run `[sys.executable, "-m", "pytest", "--continue-on-collection-errors", "--noconftest", "-o", "addopts=", ...]` on a temporary directory containing an import-failing module and setup/teardown-failing fixtures, then assert `parse_junit_xml` reads `"collection"`, `"setup"`, and `"teardown"`.

## Rejected alternatives
- **Forbidding file-level collection error repair in the spec**: Makes unchanged-test repair inconsistent with the existing changed-test error rule and rejects valid repairs where head passes all tests of the file.
- **Parsing hand-written JUnit XML only**: Leaves pytest message changes undetected until CI breaks in production.
