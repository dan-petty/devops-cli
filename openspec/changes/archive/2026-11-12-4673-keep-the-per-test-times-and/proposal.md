# Proposal: #4673

## Why
The test shards of CI print only their 10 slowest tests and write no JUnit XML report. Thus each CI saving outside those 10 rows is an estimate. The shard logs show skips with no reason, because the shard row does not ask pytest for `-rs`. The split by measured time (#4250) and a tighter per-test bound in CI need the time of each test. Closes #4673.

## What Changes
- The test row of `devops ci --shard <n> --shards <total>` adds `-rfEs` and `--junitxml=.data/junit.xml` to its pytest command. The log of a shard gives the reason of each skip. The report holds each test of the shard with its time.
- `-r` of pytest replaces its default `fE`, so the row asks again for the failed (`f`) and error (`E`) tests. With `-rs` alone, the summary of a failed shard would not name the failed tests.
- The job `test-shard` of `ci.yml` uploads `.data/junit.xml` in the artifact `coverage-shard-<n>`, beside `.data/.coverage`. The step name is now `Upload Coverage Data and Test Report`.
- An unsharded run, such as a local `uv run devops ci`, writes no report and keeps the default summary.
- The command of a `devops ci` option changes, so the change carries a delta of `ci-test-shards`.

## Capabilities
- `ci-test-shards`: ADDED requirement "A shard reports the time of each test and the reason of each skip".

## Impact
- `src/devops_cli/commands/ci.py`, `src/devops_cli/config/constants.py`, `.github/workflows/ci.yml`, `tests/commands/test_ci_shard.py`, `docs/SDLC.md`.
- Each shard artifact grows by one XML file. The job `Tests & Coverage` downloads each artifact to its own folder and combines only `.data/shards/*/.coverage`, so the extra file does not change the coverage step.
- No new dependency. No change to a required check name.

## Feasibility
- `PYTEST_ADDOPTS` cannot carry the options: `build_subprocess_env` refuses it (ARCHITECTURE.md, File-write child environment, #2747). The options go on the command line of the row, which `_resolve_pytest_cmd` builds.
- `-r` is a store option with the default `fE` (`_REPORTCHARS_DEFAULT` of `_pytest/terminal.py` in the installed pytest). A value of `s` replaces the default, so the row passes `fEs`.
- pytest makes the parent folder of the `--junitxml` path, and pytest-xdist sends the report of each worker to the controller, which writes one file.
- `devops ci --only test` runs one row and does not capture its output (`capture_output = len(selected_specs) != 1`), so the `-r` summary goes to the job log.
- `actions/upload-artifact` takes more than one path and keeps the paths under their least common folder `.data/`. Thus the artifact root holds `.coverage` as before, and `junit.xml`.

## Existing Tool Considered
The built-in `--junitxml` and `-r` options of pytest and the multi-path input of `actions/upload-artifact`. No new tool and no new code beyond the options.
