# Tasks

## 1. Remove a label from a pull request in the store

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_github_store.py`.

- [ ] 1.1 Add a test in `tests/roadmap/test_roadmap_github_store.py` that `unlabel_issue` sends the delete of one label and keeps the other labels, and verify that `uv run devops ci test tests/roadmap/test_roadmap_github_store.py` fails on the base
- [ ] 1.2 Add `unlabel_issue(number, label)` to `RoadmapStore` in `src/devops_cli/roadmap/store.py`, to `GitHubRoadmapStore` in `src/devops_cli/roadmap/github_store.py` and to the in-memory store in `src/devops_cli/roadmap/memory_store.py`. Add the request to `src/devops_cli/roadmap/request_plan.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_github_store.py` passes

## 2. Add and remove the title labels in one call

Reads: `src/devops_cli/roadmap/pull_labels.py`, `src/devops_cli/roadmap/title_labels.py`, `tests/commands/test_pr_title_labels.py`. Changes: `src/devops_cli/roadmap/pull_labels.py`, `tests/commands/test_pr_title_labels.py`.

- [ ] 2.1 Add a test in `tests/commands/test_pr_title_labels.py` that `replace_pull_labels` adds the new labels and removes the old `type/*` and `scope/*` labels that the new title does not give, and verify that `uv run devops ci test tests/commands/test_pr_title_labels.py` fails on the base
- [ ] 2.2 Add `replace_pull_labels(repo, pull, old, new)` to `src/devops_cli/roadmap/pull_labels.py`. It adds the labels of `new` with `add_pull_labels` and removes each `type/*` or `scope/*` label of `old` that `new` does not give, through `unlabel_issue`, and verify that `uv run devops ci test tests/commands/test_pr_title_labels.py` passes

## 3. Label the stage job's draft pull request

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/pull_labels.py`, `tests/roadmap/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [ ] 3.1 Add a test in `tests/roadmap/test_roadmap_stage_apply.py` that the stage job labels the opened pull request, and that a label failure keeps the branch and the marks and records the failure in the job comment, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` fails on the base
- [ ] 3.2 In `src/devops_cli/roadmap/stage.py`, after `_open_pull` returns, read the labels of the title with `read_title_labels` and add them with `add_pull_labels`. Catch a `GitHubOperationError` and report it in the job comment on the item, keeping the branch and the marks, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` passes

## 4. Label the implement job's pull request from the new title

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/pull_labels.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 4.1 Add a test in `tests/roadmap/test_roadmap_implement_job.py` that `_pull_request` adds the labels of the new title and removes the stale `type/*` and `scope/*` labels of the old title, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [ ] 4.2 In `_pull_request` of `src/devops_cli/roadmap/implement_run.py`, after `client.update_pull`, call `replace_pull_labels` with the labels of the old title and the labels of the new title, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
