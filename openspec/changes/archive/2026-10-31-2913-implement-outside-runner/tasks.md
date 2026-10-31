# Tasks

## 1. run-job labels the runner Job and keeps one for each repository

- [x] 1.1 Move the fake `kubectl` of that test to `tests/support/fakes/cluster_jobs.py`, and write failing tests in `tests/commands/k8s/test_k8s_run_job.py` for the scenarios of "run-job creates a Job from the runner template": the label of the repository on the Job and its pod, a refusal while a Job with the label has not ended, an ended Job that does not block, and the dry run that lists the lookup
  - Verification: `uv run devops ci test tests/commands/k8s/test_k8s_run_job.py`
- [x] 1.2 Move `repository_label` to `src/devops_cli/k8s/cluster_job.py`; give `execute_job` and `dry_run_job` the labels; list the running Jobs of the label; move the body of `run_job` to `start_job`
  - Verification: `uv run devops ci test tests/commands/k8s/test_k8s_run_job.py tests/roadmap/test_roadmap_implement_submit.py`

## 2. The command starts the runner Job

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_implement_outside.py` for the scenarios of "A workstation starts the runner Job for one Item" and "The job runs steps only in a runner": the Job and its args, `--no-wait`, the exit code of the container, a claimed Item, an Item of another Status, a running Job, the refused options, the `--group` message, the dry run with no request, and the old refusal with no `--item`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_outside.py`
- [x] 2.2 Write `src/devops_cli/roadmap/implement_outside.py` and call it, with `start_job`, from `src/devops_cli/commands/roadmap.py`, with the options `--context` and `--wait/--no-wait`, the messages and the help text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_outside.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_dry_runs.py`

## 3. The documents and the archive

- [x] 3.1 Name the path in `k8s/README.md` and `docs/ROUTINE_TASKS.md`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`
- [x] 3.2 Archive the change
  - Verification: `uv run devops openspec archive 2913-implement-outside-runner`

## 4. Review fixes

- [x] 4.1 One lock for every spelling of a repository: `repository_label` folds the case, and the fake `kubectl` lists Jobs by the selector
  - Verification: `uv run devops ci test tests/commands/k8s/test_k8s_run_job.py tests/roadmap/test_roadmap_implement_outside.py`
- [x] 4.2 Check `--repo` before any read, refuse a dot segment in the token repository, and let a dry run ignore the options that need the runner
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_outside.py tests/github/test_github_app_identity.py`
- [x] 4.3 The Service lists the Jobs again before it creates one; the lock is best effort; a repository that the installation lacks fails in the pod with a message that names it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/github/test_github_app_identity.py`

## Workflow follow-up

- `docs/ROADMAP_WORKFLOW.md` (W1, #2909) names the path in its step 5. That document is the change of #2909.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
