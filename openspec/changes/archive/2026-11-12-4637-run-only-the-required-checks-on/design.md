# Design

## Decisions

- **A job condition on the head branch.** Each job that no rule of `main` reads gets `!(startsWith(github.head_ref, 'release-please--') && github.event.pull_request.head.repo.full_name == github.repository)` in its `if`. GitHub skips the job before a runner starts, and the job reports `skipped`. The release merge guard refuses only a failed or cancelled check, so the scheduled merge goes on.
- **The same term in each job.** GitHub reads no `env` in a job `if`, so the term is written in each job. The new invariant test reads the term as one string, so each job holds the same text.
- **Only a branch of this repository.** The second half of the term keeps the jobs on a branch of a fork with a release name. These jobs are not required, but the image scans then still run for a fork.
- **The guard is a list of the jobs that a release push starts.** The test reads every workflow that a `synchronize` of a pull request into `main` starts with the four release files. It allows the jobs whose name is a required check, the jobs that they need, and the jobs of `codeql.yml`. Three other jobs hold no term: `Test Job Duration` and `Dependency Freshness` run on no pull request, and the `Plan Check` runs only for a plan of the Service's bot, which the test reads with `_runs`. A job that moves to a workflow of its own with a `paths` filter that holds `pyproject.toml` or `uv.lock` fails the test until it gets the term.
- **The ADR 0004 note, not a supersession.** ADR 0014 amends ADR 0004 and keeps two of its decisions. The note at the top of ADR 0004 gets the two missing facts, as ADR 0025 asks for an ADR in force.

## Rejected alternatives

- **A `branches-ignore` filter on `pull_request`.** GitHub reads `branches` and `branches-ignore` of `pull_request` against the base branch, not the head branch, so the filter cannot tell the release pull request from another pull request into `main`.
- **A path filter that leaves out `pyproject.toml` and `uv.lock`.** These files are real image inputs: a topic pull request that changes a dependency must build the images.
- **A first job that decides for the other jobs.** It takes one more runner on each push of each pull request, and each job then needs it. The condition on each job takes no runner.
- **An evaluator of GitHub expressions in the test.** The project has none, and no maintained Python library evaluates them. The term is a fixed string, so the test reads it as one.
