# Design

## Decisions

- **Each test module declares what it counts in a module-level `REGISTRY_COUNTS` constant of plain literals.**: The declaration sits beside the test that enforces it, so a reviewer sees both in one diff, and an `ast` reader reads it without importing the module.
- **The table builder parses the declarations with `ast` and never imports a test module.**: The stage job runs without the test dependencies, and no test code runs inside the job.
- **A plan matches a counted item by a token of its task text and its changed paths, such as `DEFAULT_ROADMAP_`, an enum name or a table name.**: The plan text is what `check_proposal` already holds, so the check is deterministic and needs no test run.
- **A listed place is satisfied only by a task whose text names the declared path.**: It shows the one task that covers the entry and keeps an unrelated task from hiding a missing registry entry.
- **The path-existence check runs as a pure function over Python docstrings and spec files, called by `check_proposal` and by a unit test.**: It refuses a bad plan at stage time and still has an offline test that reads no network and no cluster.
- **The docstring and spec check stays out of `docs/TELEMETRY.md`, and the one stale sentence in it is corrected in this change.**: The issue's acceptance criteria cover docstrings and specs, and the doc's sentence holds the concrete stale path that the issue cites.
- **The new code lives in `src/devops_cli/roadmap/stage/stage_registry.py`.**: It keeps the declaration reader and the path scanner apart from the gate module, which the tests of `check_proposal` already cover.
- **The stage context includes the `Registry places` section built in `src/devops_cli/roadmap/stage/stage.py`.**: It adds the matching test and table places to the model request context without importing test modules.

## Rejected alternatives

- **Import the test modules at stage time to read their tables.**: The stage job runs in the runner image without the test environment, and importing a test module runs test code.
- **Keep a hand-written table of registries in `src/devops_cli/roadmap/stage/stage_change.py`.**: Acceptance criterion 4 of #3254 forbids a hand-copied table, and the `LIMITS` table of `tests/roadmap/test_roadmap_limit_classes.py` already goes stale against `config/constants.py`.
- **Run the test suite inside the stage job to discover missing entries.**: The suite needs the full test environment and minutes of run time, and the stage job holds a budget of tool calls and tokens.
- **Scan every Markdown file under `docs/` for stale test paths.**: `docs/TELEMETRY.md` is generated from `INSTRUMENTS` in `src/devops_cli/telemetry/instruments.py`, so a scanner over docs would flag generated text that the change does not own.
- **Extend the mirror-folder rule of #3189 to a test added to an existing module.**: The acceptance criteria of #3254 name registry entries and test paths only; `tests/invariants/test_change_folders.py` holds the mirror rule and #3189 stays a related item.
