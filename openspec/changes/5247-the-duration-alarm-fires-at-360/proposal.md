# Proposal: #5247

## Why

AGENTS.md rule 5 makes a check that averages more than 5 minutes a P0 bug. On 2026-10-23 the owner allowed 1 minute of tolerance for the variation of the runners, but `devops ci job-time` still fails at 300 s, and a breach files no issue: the daily `Test Job Duration` job only turns red. On 2026-11-13 it read a mean of 316 s for `Tests & Coverage` on `main`, so `main` is red and this is a P0 bug. The cause of the time is the split of the four test shards by lines of test code: a short module with slow tests makes one shard long, and each change of the tree moves modules between shards. In one run the four shards took 160 s to 341 s. The pin of pytest-split stays in the dev group with no use. Closes #5247.

## What Changes

- `devops ci job-time` fails when the mean is over 360 s by default: the 300 s target of AGENTS.md rule 5 (`CONST_CI_TEST_BUDGET_SECONDS`) plus 60 s of tolerance (`CONST_CI_TEST_BUDGET_TOLERANCE_SECONDS`). The warning of a local gate stays at 300 s.
- `devops ci job-time --file-issue`: when all the wanted runs were read and the mean is over the limit, the command comments on the open issue whose body holds the alarm line of the check, or files one with the labels `type/bug`, `scope/ci` and `priority/p0-critical`. The issue search finds the line, so a changed title or label files no second issue.
- The job `job-time` of `ci.yml` runs with `--file-issue` and gets `issues: write`.
- `shard_test_files` weighs each test module by its recorded seconds in `tests/module_durations.json`. A module that the record does not hold weighs its lines at the recorded seconds per line. With no record, every module weighs its lines, as before.
- The new command `devops ci durations` writes the record from the JUnit reports of the shards of the last 20 push runs of `main`, which `ci.yml` already uploads (#4673). `gh run download` gets the artifacts. The JUnit reader of `ci/fail_to_pass.py` now keeps the time of each test.
- `GitHubClient` gets `get_run_artifact_names` and `create_issue`.
- The record of the last 20 runs is committed.
- The pin `pytest-split==0.11.0` and its lock entry go.
- AGENTS.md rule 5, docs/TESTING.md (Run time), the knowledge base task `ci_quality_gate.md` and the comments of `ci.yml` state the new limit, the issue and the split.
- A command, an option and a message change, so both capabilities carry a delta. The change fits one pull request.

## Capabilities

- `ci-job-time` (modified): the default limit, the P0 issue of a breach, and the permissions of the job.
- `ci-test-shards` (modified): the split by recorded seconds, and the command that writes the record.

## Impact

- A replay of the last 20 runs of `main` gives a mean of 284 s with the new split, under the 300 s target, against the 316 s that the runs took.
- The `Test Job Duration` job can write issues of this repository. It writes at most one comment or one issue each day.
- A new test module joins a shard with no other step. A stale record only unbalances the shards and drops no test.
- No setting, secret or repository setting changes. The required checks keep their names.

## Feasibility

- Command run on 2026-11-13, `uv run devops ci job-time` at `main` 54cf0a526: 20 runs, mean 316 s, mean queue 7 s, exit 1 against the limit of 300 s. The scheduled run 43370174775 failed with the same text (evidence comment on #5247).
- Actions API, `GET /repos/dan-petty/devops-cli/actions/runs/<id>/artifacts` for each of the 20 runs: each run holds `coverage-shard-1` to `coverage-shard-4`, and each artifact holds `junit.xml`. Each `testcase` has a `time` and a `classname` that names the module path with dots. All the tests of the 80 reports map to the 1,194 test modules of the tree.
- Actions API, jobs of the same runs: the shard jobs took 157 s to 341 s, the join job 35 s to 52 s. A shard job is about 44 s of setup plus the pytest session, and the session is about 18 s plus 0.28 of the summed test seconds of the shard (fit over the 80 shards).
- Replay of the 20 runs (scratch script over the downloaded reports): each shard keeps the setup and the residual of its own runner, and only its modules change. The split of each run reproduces the 316 s. The split by lines of the current tree gives 298 s. The split by recorded seconds, with the weights of each run taken from the other 19 runs, gives 284 s. A perfect balance gives about 274 s.
- `gh run download --pattern` unpacks each matched artifact into a folder of its name. The run of `uv run devops ci durations --runs 20` that wrote the committed record used it.
- The issue search finds text inside an HTML comment of a body (#2419). `review/filed_findings.py` and `research/sweep.py` find their issues the same way.
- The owner's words of 2026-10-23, which #4250 quotes: a mean over 5 minutes, with 1 minute of tolerance for build variation, is a P0 blocking bug.
- `git grep pytest-split` at `main` finds the pin, the lock entry and a recorded census fixture only. The shard command holds no `--splits` (spec `ci-test-shards`).
- `tests/invariants/test_agents_md.py` passes with AGENTS.md at 6,500 of 6,500 characters.

## Existing Tool Considered

- pytest-split 0.11.0 (MIT, last release 2026-02-03) splits by stored durations, but it selects the tests of a group after it collects the whole suite. Each xdist worker of each shard then collects every file, which cost 13.5% of the CPU of a run (#3810). Its `.test_durations` file holds each test, about 19,000 lines. It covers no part of this change, so its pin goes.
- gh (`gh run download`) downloads and unpacks the artifacts, through `run_gh`, which paces it. The JUnit reader of `ci/fail_to_pass.py` (stdlib `html.parser`) reads the times, and pydantic reads the record.
- The issue search of GitHub, through `GitHubClient.search_issue_bodies`, finds the open alarm issue, as the review and research filers do.
- Built instead: the weight of a module, the record and its writer, and the alarm issue. Cost: about 150,000 tokens and 3 hours to build; upkeep is a run of `devops ci durations` when the alarm nears the limit.
- Deleted: the rule that the split stores no data, and the pin and lock entry of pytest-split.
