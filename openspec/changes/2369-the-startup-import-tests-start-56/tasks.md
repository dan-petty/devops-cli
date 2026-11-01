# Tasks

## 1. Replace -X importtime with sys.modules dump in the probe

Reads: none. Changes: `tests/commands/test_cli_startup_imports.py`.

- [ ] 1.1 Write a test that asserts the subprocess args of _probe_startup_imports do not include -X importtime. The test mocks subprocess.run and checks the args list. Before the change, the args include -X importtime, so the test fails, and verify that `uv run pytest tests/commands/test_cli_startup_imports.py -n 0 -x -q` fails on the base
- [ ] 1.2 Modify _probe_startup_imports to build a -c script that imports the entry point, runs the command, then prints sorted(sys.modules.keys()) to stdout. Remove -X importtime from the subprocess args. Parse stdout instead of stderr for the module list, and verify that `uv run pytest tests/commands/test_cli_startup_imports.py -n 0 -x -q` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Add timed re-probe for the failure diagnostic message

Reads: none. Changes: `tests/commands/test_cli_startup_imports.py`.

- [ ] 2.1 Write a test that asserts _probe_startup_imports_timed exists and returns a list of (module, cumulative_seconds) pairs sorted by cumulative_seconds descending. Before the change, this function does not exist, so the test fails, and verify that `uv run pytest tests/commands/test_cli_startup_imports.py -n 0 -x -q` fails on the base
- [ ] 2.2 Add _probe_startup_imports_timed that runs the same argv with -X importtime and parses stderr for the ten slowest imports by cumulative seconds. Update the assertion helpers: when the module count exceeds the limit, call _probe_startup_imports_timed and include its result in the assertion message, and verify that `uv run pytest tests/commands/test_cli_startup_imports.py -n 0 -x -q` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
