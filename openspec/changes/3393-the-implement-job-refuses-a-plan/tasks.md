# Tasks

## 1. Read the plan of an item and refuse it when the check finds a problem

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/planned.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 1.1 Add to `tests/roadmap/test_roadmap_implement_job.py` a test that a Staged item whose branch plan holds the placeholder task `1.1 x` gets no target and a reason with the first problem, a test that a Planned item whose default-branch plan holds the placeholder gets no target and no branch, and a test that a plan which passes the check gets a target
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [ ] 1.2 Add one reader in `src/devops_cli/roadmap/implement.py` that builds a `StageProposal` from `openspec/changes/<change>/` at the staged branch or at the default branch, and call `check_proposal` with the base capability names, the base requirement names, the item body and the tree. Call it from `_Judge.judge` for a Staged and a Planned item, before `_planned_target` makes a branch, and return the first problem as the reason of a `LeftOut`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 2. Name the plan problem in the page of the implement job

Reads: `src/devops_cli/roadmap/implement.py`, `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [ ] 2.1 Add the plan check to the list of reasons that the implement job leaves an item out, in the page that the help of `devops roadmap implement` names, so a person reads why an item with a refused plan waits
  - Verification: `uv run devops ci docs` passes
- [ ] 2.2 The page `docs/roadmap/implement.md` names the plan check among the reasons that the job leaves an item out, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
