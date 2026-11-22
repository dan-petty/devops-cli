# Design

## Decisions

- **Check each of the six real jobs of the two images of #6522.**: The Actions API gives `Build`, `Verify` and `Attest & Tag` of each image as separate jobs, and each one has a timeout above 360 s (20, 15 and 10 minutes), so each one can break AGENTS.md rule 5. The plan of #6522 names `MCP Server Image` and `Runner Image`, so the checks are the three jobs of each of these two images.
- **Write the six names as the API gives them.**: A literal tuple of `MCP Server Image / Build` and the others matches what the API returns, and a search of the code for a job name of a run finds it.
- **Read the jobs of a run one time for all checks of one workflow, branch and count.**: On the base, one release check took 38 s for about 48 job reads. Six separate reads take about 230 s of the 5 min job, and use six times the requests of the hourly quota of `GITHUB_TOKEN`. One shared read takes about the time of one check.
- **Stop a read after the jobs of 100 runs (`DEFAULT_CI_JOB_TIME_MAX_RUNS`).**: The image jobs run only on a push that makes a release. On 2026-11-22, 21 of the last 100 runs of `release.yml` were release runs, and the tenth release run was run 48, so 100 runs give the 10 release runs room twice over. 100 runs are one page of the listing. A wrong or renamed job name then costs 101 requests and ends with a short read, not 2,385 requests and a timeout.
- **Put the bound in `config/defaults.py`.**: The client of the `github` package and the command of the `commands` package both read it, the one to stop the read and the other to name it in the short-read message and the dry-run plan (CONTRIBUTING.md, Naming, Constant).
- **Give the `--runs` options of `job-time` and `durations` the maximum of the bound.**: A read never gives more than 100 runs. Without a maximum, `job-time --runs 101` always exits 1, and `durations --runs 101` reads fewer runs with no message. A usage error names the bound before any request.
- **Keep `get_job_run_times` for one job.**: The stage premise check and `devops ci durations` read one job of `ci.yml`, so they keep their call, and it reads through the shared read with one job.
- **Make the fake give the names and the shapes of the live API.**: Each release run of the fake holds `Release Please`, `Upload Release Assets`, the DevContainer jobs and the three jobs of each of the three images, and each run between two releases holds only skipped jobs and `${{ matrix.title }} Image`, as runs 44977064803 and 44979901604 show.

## Rejected alternatives

- **Time one image as the span from the first start to the last end of its jobs.**: The span holds the wait between the jobs for a runner, which the check does not count (#4634), and one check for three jobs hides which job is slow.
- **Check the jobs of `Service Image` and of the DevContainer image too.**: The plan of #6522 rejects `Service Image` because its mean is inside the bound, and its jobs took 58 s to 114 s on 2026-11-22. The DevContainer image is not part of #6522.
- **Match a job by the prefix `<Title> Image /`.**: A prefix mixes three jobs into one time, and the shard rule already reads `<job> (` as a shard. Exact names keep one job as one check.
- **Stop at a page count with `max_pages=1`.**: A page count ties the bound to the page size of the listing. A count of runs states the bound in the unit of the check.
- **Bound the read at a multiple of the wanted runs.**: The acceptance of #6734 asks for a fixed count, and a multiple lets a check with a large `--runs` read the whole history again.
- **Keep the jobs of each run in a cache of the client.**: The session keeps no answer of a page that links no next page, and a hidden cache in the client gives a second state to keep correct. The shared read needs no state after it returns.
