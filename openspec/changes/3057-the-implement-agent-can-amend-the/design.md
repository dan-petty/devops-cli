# Design

## Decisions

- **Classify the defect in the step that detects it, with no extra model call.**: The step already holds the plan, the change folder and the repository, so the classification adds no round trip.
- **Record the amendment in a dedicated `## Amendments` section of the change folder's `tasks.md`.**: The issue names `tasks.md` as the record, and a separate section keeps the amendment history apart from the task checklist.
- **Route an over-budget group through `_Planner._fit` of `stage.py`.**: That is the existing split step, and the issue asks for the re-split by it rather than a second split path.
- **Post the amendment and its evidence as one pull request comment.**: The acceptance criteria ask for the amendment in the pull request comment with the evidence.

## Rejected alternatives

- **A separate classification step before the amendment.**: `read_spec roadmap-implement-step` shows a step is bounded by its inputs and its window, so a second step adds a token cost for every defect.
- **A separate amendments file in the change folder.**: The issue body names `tasks.md` as the record of the amendment.
- **A new split implementation in the implement job.**: `file_symbols src/devops_cli/roadmap/stage.py` showed `_Planner._fit` already splits groups with `StageSplit` and measures them.
