# Design

## Decisions

- **Keep the `StageProposal` and the `StageRequest`, not the `StagedChange`.**: `StagedChange` holds `StageTarget`, `Item`, `MeasuredGroup` and `RunTrace`, and only `_settle` builds it. A hit calls `_settle(target, proposal, request)` on the current commit, so the gates and the measure of the groups run again, as the issue asks. The issue text says "the gated `StagedChange`"; the rebuild by `_settle` is the same result with no second serialiser.
- **One file for each item, named by the item number, with the key inside.**: The path is `roadmap/stage/<owner>/<repo>/<number>.json`. A file holds one plan, so a new key replaces the file, and "delete the file when its key changes" needs no search for other files of the item. The planner deletes a file with another key at once, so a plan that then fails leaves no stale file.
- **Write the file after `_gated` returns a change and before the review.**: A failed review then leaves the file, and the rerun sends the planner no request. A repair round of the review changes the plan after the write; the file keeps the plan that passed the gates, and the review runs again on a hit.
- **Keep no findings in the file.**: The issue lists the findings as a field. The file is written before the review, so it has none, and a hit runs the review again, which makes new findings on the current commit. A stored finding would be stale. The file holds the key, the proposal and the request.
- **The key hashes both results of `body_hashes`, the title, the number, the model name, the toolset name and the prompt version.**: A change of the refine section changes the text that the planner reads, so the section hash is part of the key. The staged commit is no part of it, because the commit moves several times a day, and a hit runs the gates again on the new commit.
- **The prompt version is the sha256 of the texts that `load_task_prompt` gives for `roadmap_stage_change.md`, `roadmap_stage_split.md`, `roadmap_stage_tools.md` and, for the toolset `extended`, `roadmap_stage_tools_extended.md`.**: The code has no prompt version, and the issue defines it as this hash. A test replaces `load_task_prompt` in the module and sees a new key.
- **A plan file that the gates refuse on a hit goes back to the model once.**: The kept plan is the first reply of the normal flow. If the new commit makes the gates refuse it, the existing return of a refused reply sends the plan and the problem to the planner once. So a hit never fails an item that a miss would plan.
- **The budget is not in the key.**: A hit with a smaller `step_tokens` can end as `OverBudget` or ask for one split, and `_settle` handles both. The kept `StageRequest` holds the budget of the first run, and `_settle` reads the budget of the planner.
- **The model name is the name of the task `stage` from the settings, and the toolset is `roadmap.stage.toolset`.**: Both are read at the call of `plan_stage`, in the place where the planner is made, and passed to the planner with the directory. `plan_item` passes none, so the golden set keeps no file and asks the model each time (#3028).
- **An unreadable file raises `RoadmapStageError` with the file name.**: It is the rule for `IntakeRecord`, and AGENTS.md rule 2 forbids a swallowed error. The item fails with the path in the reason, and a person deletes the file.
- **`read_plan_record(path, key)` reads the key first and checks the rest only when the key is the same.**: A file with another key is a miss and the planner deletes it, so a file that older code wrote with another `StageProposal` schema does not fail the item when a prompt, the model or the toolset changed too. A file that is no JSON object with a `key` text raises. A file with the same key that does not match `StagePlanRecord` raises.
- **The counter counts in the planner, at the read and at the write.**: `miss` and `hit` at the read, `written` at the write. A miss that plans and writes adds 1 to `miss` and 1 to `written`. The counter has 3 series, and it counts also a `--plan` run, because `--plan` and `--confirm` both plan through `_Planner`.
- **The writer deletes the file in `StageWriter._stage` after `_stage_one` succeeds.**: A failed write keeps the file, so the next run plans from it.
- **No setting.**: The change adds no setting, so the ConfigMap needs no change (`RoadmapStageConfig` has `extra="ignore"`).

## Rejected alternatives

- **Store the plan in the item record.**: The issue states that the record holds marks only (`stage.sha`, `stage.groups`, `stage.text_hash`), and a plan is too large for a mark.
- **Key by the staged commit.**: The issue drops it: `main` moves several times a day, so the key would rarely hit.
- **Serialise `StagedChange` itself.**: It holds `StageTarget`, `Item`, `MeasuredGroup` and `RunTrace`, which are dataclasses with no model; `StagedChange` would need a second serialiser. `_settle` already builds it from the two models.
- **Fall back to a new model request when the file is unreadable.**: This swallows the error (AGENTS.md rule 2) and hides a corrupt volume.
- **An external cache library such as `diskcache`.**: It adds a dependency and a store format for one JSON file for each item, and ADR 0008 maps these files to Argo artifacts one to one.
- **Hold the findings in the file and skip the review on a hit.**: The commit moves between runs, so the review of the first commit does not judge the new one. The review runs again.

## Risks

- The hit rate is unmeasured. The counter measures it. A runner pod without the volume `roadmap-service-home` gets only misses.
- A rollout that changes the `StageProposal` schema and leaves the key the same (no change of a prompt, the model or the toolset) makes the stored files unreadable. The items with such a file fail with the file name until a person deletes it. The key is read first, so a rollout that also changes a prompt gives a miss and no failure.
