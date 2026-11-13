# Design

## Decisions

- **Limit = target + tolerance.** `CONST_CI_JOB_TIME_LIMIT_SECONDS` is the sum of `CONST_CI_TEST_BUDGET_SECONDS` (300 s) and `CONST_CI_TEST_BUDGET_TOLERANCE_SECONDS` (60 s), and it is the default of `--limit`. The target stays 300 s: the local gate still warns above it, and the split aims under it.
- **One issue for one breach.** The alarm issue holds the line `<!-- devops-ci-job-time: <job> of <workflow> on <branch> -->`. A run over the limit searches the issues whose body holds `devops-ci-job-time` and counts only an open issue with the line of its own check. It comments on the lowest such number, or files a new issue when none is open. The title holds the mean and the limit for a person, and no reader uses it as a key, because the roadmap Service can change a title and a person can change the labels.
- **The alarm stays red.** The command still exits 1 over the limit, with or without the issue. The issue holds the work, and the red row shows the state of `main`.
- **No issue without a full read.** A short read or a mean inside the limit makes no search and no write.
- **A record per module, in the tree.** `tests/module_durations.json` maps the path of each test module to its mean seconds, in tenths of a second, one module a line. Every runner reads the same file from the same commit, so the four shards compute one split. The split needs a weight per module, not per test.
- **Fallback by lines at the recorded rate.** A module that the record does not hold weighs its lines times the recorded seconds per line of the recorded modules of the tree. A large new module stays heavy, and a tree with no record splits by lines as before. A recorded module that the tree does not hold is in no shard and is not in the rate.
- **The mean over the runs that ran a module.** Runner speed changes from job to job, and the mean of 20 runs smooths it. A module that a run did not run, such as one of a failed shard, takes no zero into its mean.
- **The writer reads CI, and a person or agent commits.** `devops ci durations` reads the reports of the last 20 runs, the same window as the alarm, and writes the file. No job of CI writes to `main`.

## Rejected alternatives

- **pytest-split.** It selects tests after it collects the whole suite in each shard. #3810 measured 31.8 s of CPU in each of 16 workers for that collection, 13.5% of a run. Its file holds each test (about 19,000 lines).
- **Download the reports in each shard at run time.** The four shards would read the newest run at different times, and two runners that read two runs compute two splits that drop or repeat modules (#4250, scope of 2026-11-11).
- **The mean weight for a new module.** The replay found no gain over the lines at the recorded rate, and a module of 2,000 lines would weigh the same as one of 20 lines.
- **A fifth shard.** #4473 closed as not planned: each shard adds jobs under the cap of 20 concurrent jobs of the account. The replay shows that four balanced shards reach 284 s.
- **The title as the key of the issue.** The roadmap Service retitles issues, so the next run would file a second issue.
- **A list of every open issue.** The repository holds about 750 open issues, 8 pages a run; one search request finds the alarm line.
