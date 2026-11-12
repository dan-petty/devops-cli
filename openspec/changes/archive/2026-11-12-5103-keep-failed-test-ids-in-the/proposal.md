# Proposal: #5103

## Why
The shard test step of the Service Image Tests workflow gives pytest the option `-rs` (#4642). The `-r` option of pytest replaces its default report characters `fE`. Thus the short test summary of a failed shard gives only the skip reasons, and it does not name the failed and error tests. AGENTS.md rule 14 tells us to keep the failed test IDs in the output. Closes #5103.

## What Changes
- The shard test step of `.github/workflows/service-image-test.yml` gives pytest `-rfEs` in place of `-rs`. The summary gives the reason of each skip and names each failed and error test again.
- The workflow shape test reads the option from `CONST_CI_SHARD_SUMMARY_CHARS`, the summary characters of the `devops ci` shard row (#4673). The two kinds of shard thus keep one summary, and a change of one side fails the test.
- `docs/SDLC.md` says that a shard of the Service image names each failed test.

## Capabilities
- `ci-service-image-tests`: MODIFIED requirement "The shards load one build of the Service image".

## Impact
- `.github/workflows/service-image-test.yml`, `tests/commands/test_ci.py`, `docs/SDLC.md`.
- The log of a shard grows by one line for each failed or error test. A green shard log does not change.
- No new dependency. No change to a check name. The workflow is not a required check.

## Feasibility
- `-r` is a store option with the default `fE` (`_REPORTCHARS_DEFAULT` of `_pytest/terminal.py` in the installed pytest 9.1.1), so a value of `s` replaces the default.
- A probe with `-q -n 2` on one passing, one failing and one skipped test: `-rs` gives only `SKIPPED [1] test_rs_probe.py:4: why skipped`. `-rfEs` gives also `FAILED test_rs_probe.py::test_bad - assert 1 == 2`.
- `pyproject.toml` `addopts` has no `-r` option, so the command line of the step sets the summary alone.

## Existing Tool Considered
The built-in `-r` option of pytest. No new tool and no new code beyond the option.
