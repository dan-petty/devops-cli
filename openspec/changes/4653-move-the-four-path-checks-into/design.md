# Design

## Decisions
- One workflow file for each check, named after its job id. A check run takes its name from the job, so each check keeps its name. The workflow `name` is the check name too, so the Actions list shows the same word.
- Each `paths` filter holds the paths of the old step filter. The workflow file takes the place of `ci.yml`, so a change to a check runs that check, and a change to `ci.yml` runs none of the four. Rule Pack Tests and Third-Party Image Scan did not watch `ci.yml` before; they now watch their own file, as `service-image-test.yml` does.
- The trigger types are those of `ci.yml`: opened, synchronize and reopened, into `main`. `ready_for_review` and `edited` change no file, so they start no run.
- The concurrency group is `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress`. Each workflow has one event, so the group needs no event name.
- `permissions: {}` at the top, and `contents: read` on the job, as in `pages.yml`. No job reads the pull request now, so `pull-requests: read` goes.
- Each workflow repeats `DO_NOT_TRACK: "1"` of `ci.yml`. The two workflows that run uv also repeat `UV_MANAGED_PYTHON: "1"`, which `test_github_workflows_name_their_runner_and_use_managed_python` requires.
- The job limits stay as they are. #4677 sets the job limits of all CI jobs; the change that merges second carries the value of the other into the moved jobs.
- The tests use `_starts_on` of `tests/invariants/test_workflow_contracts.py`, which evaluates `paths` patterns as GitHub documents, to show which workflows a changed file starts.

## Rejected alternatives
- Keep the jobs in `ci.yml` behind a job-level `if` on the output of one filter job. The filter job still takes a runner on each push, and the four jobs then wait for it.
- `dorny/paths-filter` or `git diff` in a step, as now. The job takes a runner for each push: 4 jobs for each run in the measured window, for 0.67 jobs of work.
- Add `on.pull_request.paths` to `ci.yml`. The filter applies to the whole workflow, so the required checks Static Analysis and Tests & Coverage would stay "Pending" on a pull request that the filter skips, and the pull request could not merge.
- Move Docs Site Build into `pages.yml`. That workflow deploys from `main` with one concurrency group `pages` and no cancel. A pull request run in it would wait for a deployment, and a deployment for a pull request run.
