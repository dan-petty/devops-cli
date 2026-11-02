# Proposal

## Why

The stage job and the implement job open or update pull requests through their own client, so their pull requests get no `type/*` or `scope/*` label from the title (#2777). `devops pr create` already labels its pull request from the title (#2748), and the two jobs must do the same.

## What Changes

- The stage job adds the `type/*` and `scope/*` labels of the title after `_open_pull` succeeds.
- A label failure in the stage job is reported in the job comment on the item, and the remote branch and the job marks stay.
- The implement job adds the labels of the new title after it sets the title and body.
- The implement job removes a `type/*` or `scope/*` label that the old title gave and the new title does not give.
- `RoadmapStore` gains `unlabel_issue`, with the GitHub and in-memory stores and the request plan.
- `pull_labels` gains `replace_pull_labels`, which adds the new labels and removes the stale ones.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Stage job labels its draft pull request from the title
- `roadmap-implement-job`: Implement job labels its pull request from the new title

## Impact

- Code: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/pull_labels.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/implement_run.py`
- Tests: `tests/roadmap/test_roadmap_github_store.py`, `tests/commands/test_pr_title_labels.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/pull_labels.py` showed `read_title_labels` and `add_pull_labels`, the pieces that #2748 added and that this change reuses.
- `read_file` of `src/devops_cli/roadmap/stage.py` lines 1054-1068 showed `_open_pull`, which deletes the remote branch when GitHub refuses the pull request. The label call goes after it, so a label failure never reaches that delete.
- `read_file` of `src/devops_cli/roadmap/implement_run.py` lines 580-591 showed `_pull_request`, which calls `client.update_pull` with the new title and body. The label write goes after that call.
- `search_code` for `unlabel` and `label_issue` found no removal of a label, so the change adds `unlabel_issue` to the store and `replace_pull_labels` to `pull_labels`.
- `list_files` of `tests/roadmap` showed `tests/roadmap/test_roadmap_implement_job.py`, which holds the test of the delivery title, and no `test_roadmap_implement_run.py`.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` for the stage path, and `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` for the implement path.

## Existing Tool Considered

No new tool is needed. The change reuses `title_labels` and `declared_label_names` in `src/devops_cli/roadmap/title_labels.py`, `read_title_labels` and `add_pull_labels` in `src/devops_cli/roadmap/pull_labels.py`, and `RoadmapStore.label_issue`, all added by #2748. It adds one small store method, `unlabel_issue`, about 10 lines, because no code removes a label today.
