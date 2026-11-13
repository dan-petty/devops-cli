# Tasks

## 1. Behavior: the alarm limit and the P0 issue

- [x] 1.1 Add the failing tests: the default limit is 360 s (330 s and 360 s pass, 361 s fails), `--file-issue` files one P0 issue when no open issue holds the alarm line, comments on the open one and files no second, makes no request inside the limit or on a short read, and the dry run lists the search and both writes; the job of `ci.yml` runs with `--file-issue` and `issues: write`
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py`
- [x] 1.2 Add `CONST_CI_TEST_BUDGET_TOLERANCE_SECONDS` and `CONST_CI_JOB_TIME_LIMIT_SECONDS`, `raise_alarm` in `ci/job_time.py`, `GitHubClient.create_issue`, the option `--file-issue` and its messages, and the permission and option in `ci.yml`
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py tests/commands/test_ci.py`
- [x] 1.3 Check the workflow
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Behavior: the split by recorded seconds and its record

- [x] 2.1 Add the failing tests: a short module with a long recorded time is alone in its shard, a module without a record weighs its lines at the recorded rate, a deleted module is ignored, the committed record maps test modules to seconds, and `devops ci durations` writes the mean of each module over the runs that hold reports, skips a run without shard artifacts, exits 1 with none, and lists its requests in a dry run
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py tests/ci/test_ci_durations.py`
- [x] 2.2 Weigh the modules in `shard_test_files` by `recorded_durations`, keep the time of each test in the JUnit reader, add `ci/durations.py`, `GitHubClient.get_run_artifact_names` and the command `devops ci durations`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py tests/ci/test_ci_durations.py tests/ci/test_fail_to_pass.py`

## 3. Data: the record of the last 20 runs

- [x] 3.1 Write `tests/module_durations.json` from the last 20 push runs of `main`, and mark it generated in `.gitattributes`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`

## 4. Deletion: the unused pytest-split pin

- [x] 4.1 Remove `pytest-split==0.11.0` from the dev group and lock again
  - Verification: `! git grep -n pytest-split -- pyproject.toml uv.lock`

## 5. Documents

- [x] 5.1 State the limit, the tolerance, the P0 issue and the split in AGENTS.md rule 5, docs/TESTING.md (Run time), the knowledge base task `ci_quality_gate.md` and the comments of `ci.yml`, and regenerate the command reference
  - Verification: `$ uv run devops docs generate --check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
