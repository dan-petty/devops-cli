# Proposal: #6654

## Why

`devops roadmap step scaffold` makes the branch of an item on GitHub through the refs API, with no commit (#5499). No Job, Service row, manifest or workflow runs it; only its CLI registration names it. The first push of a job makes the branch. Closes #6654.

## What Changes

- Delete the step (`roadmap/steps/scaffold.py`), its command, its registration, its help text and its tests.
- Delete the record key `scaffold.branch` (`ScaffoldRecordKey`). The stage job resumes an App-only branch of a Ready item by its `stage.pending` mark alone, as no code writes `scaffold.branch` now. A record that still holds the key keeps it as the key of another version.
- Delete `GitHubClient.create_ref`, which only the step called, and its test.
- Delete the section of the step in `docs/roadmap/stage.md` and its row in `docs/ROADMAP_WORKFLOW.md`, and generate the reference again.

The command goes, so the change carries a spec delta.

## Capabilities

- `roadmap-stage/scaffold`: REMOVED each requirement of the step. The requirement 'The orphan cleanup keeps an App-only branch of a Ready item' stays: it is a rule of the stage job.

## Impact

`devops roadmap step scaffold` no longer exists. No automation called it. The change fits one pull request.

## Feasibility

- `git grep` over `src`, `tests`, `docs`, `openspec/specs`, `k8s` and `.github` found the readers: the registration, the help text, the record key in `stores/store.py` and `stage/stage.py`, `GitHubClient.create_ref`, the two documents, the spec and the tests. No manifest or workflow names the step.
- ADR 0021 names neither the step nor its resume rule, so no line of its Status History changes.

## Existing Tool Considered

The change deletes code. `git push` makes a branch, so no tool is needed.
