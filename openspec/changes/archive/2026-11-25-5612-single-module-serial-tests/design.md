# Design

## Decisions
- **Return `"0"` in `_narrowed_workers` when `len(targets) == 1` before calling `_collected_test_count`**: In `src/devops_cli/commands/ci.py:2162-2169`, check `len(targets) <= 1` (since empty targets already exited early) right after `cap <= 1`, so any narrowed run resolving to one test module uses `-n 0` and skips starting a `--collect-only` pytest subprocess.
- **Keep the explicit `-n` override and multi-module collected-test rule unchanged**: Calling `devops ci test -n <k> <path>` still bypasses `_narrowed_workers` at `src/devops_cli/commands/ci.py:2262`. Two or more target modules (`len(targets) >= 2`) continue through `_collected_test_count` up to `DEFAULT_CI_TEST_SERIAL_MAX_TESTS`.
- **Update existing single-file collection tests to pass two modules**: Existing tests in `tests/commands/test_test_selection.py:748-845` and `tests/commands/test_ci_repeat.py:168-200` intentionally exercise collection behavior (`timeout`, `returncode=5`, `repeat` collection); passing two target modules keeps those behaviors covered after single-module runs skip collection.

## Rejected alternatives
- **Add a persistent test duration cache**: Rejected in `#4472` (`docs/TESTING.md:186`) and `#5612` because the project keeps no runtime duration cache and first runs would lack duration data.
- **Raise `DEFAULT_CI_TEST_SERIAL_MAX_TESTS`**: Rejected because a slow selection across multiple files over any threshold still suffers collection overhead while a fast single module just past the threshold still triggers 4 workers.
- **Override explicit `-n` when targeting one module**: Rejected because `src/devops_cli/commands/ci.py:2262` preserves explicit `-n` as the escape hatch when a single module is unusually slow.
