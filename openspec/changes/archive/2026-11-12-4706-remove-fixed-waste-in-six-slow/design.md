# Design

## Decisions

- The documented argv test calls `collect_documented_argv_references` and `describe_unresolved_references`, the two parts of `check_documented_argv`. `check_documented_argv` stays in `src/`: `DocGenerator.check_docs` calls it, and the docs CLI tests run that path.
- The docs CLI test keeps its three calls that pass (`generate`, `check`, `generate --check`) and the call with an unknown format. The JSON export runs once in the docs tests, in `test_docs_cli_dry_run_and_format_helpers`, which reads the `groups` key of the file that it writes.
- The forage dry run gets a directory of one `pyproject.toml` with `--repo`. The directory is not a git repository: `docs/TESTING.md` says that tests start no real git, so the test runs no `git init`. Forage still runs its one `git rev-list` through the process runner, which fails at once outside a repository.
- `FORAGE_COMMAND` stays in `NO_EXTERNAL_REQUEST_COMMANDS`, so the tests of the dry-run class and of the gaps file still cover it.
- `malformed_endpoint` calls `shutdown(SHUT_RDWR)` before `close()`. The join uses `THREAD_HANDOFF_BOUND_SECONDS`, as `docs/TESTING.md` asks for a wait on another thread, and the fixture fails when the thread is still alive.
- The memory test keeps `BUDGET_BYTES`, `ANSWER_BYTES`, `SLACK_BYTES` and `EARLY_ROUND`. Only `ROUNDS` falls from 200 to 50.

## Rejected alternatives

- A patch of `check_documented_argv` and `check_source_argv` in the docs CLI test. These checks take most of its time, but `tests/invariants/test_source_tree.py` bans a patch of a devops-cli name, and the plan keeps the `check` and `--check` paths.
- A real `git init` in the forage test. It follows the plan text ("a small tmp git repository"), but `docs/TESTING.md` says that tests start no real git. A plain directory removes the same 40 `git log` calls.
- A `git_fake` transcript for forage. It needs a new scenario and recording for a test that checks only the exit code of a dry run.
- 20 rounds for the memory test. A store with no byte bound then grows 10 MiB against a slack of 6 MiB, which is too close to the slack.
- A faster `hand_written_documents` in `src/devops_cli/docs/inventory.py`. Its glob matches take a large part of the docs tests, but the change is in `src/` and has its own issue, #4979.
