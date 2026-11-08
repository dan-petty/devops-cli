# Design

## Decisions

- **Append a `### Plan reader and gate` section to the context in `_Planner._request`, after the `### Registry places` section.**: `_request` builds the request context, and `collect_context` is shared with the refine round, so a stage-only section stays out of the refine requests.
- **Name `plan_read.read_change`, `plan_read.tree_files`, `plan_read.files_at`, `plan_read.change_root` and `stage_change.check_proposal`, and create no reader.**: These four readers and the gate exist at the staged commit, so the plan names them and spends no tokens on code that exists.
- **Name `plan_read.files_at` and `plan_read.tree_files` and add no `file_texts_at` reader.**: No commit holds `plan_read.file_texts_at`; `files_at` returns the text of named paths at a revision, and `tree_files` gives the paths that it reads.
- **Put the rule in `src/devops_cli/ai/tasks/roadmap_stage_change.md`, the prompt that `_CHANGE_TASK` names.**: The stage planner reads that prompt, so a rule there reaches every plan of the job.
- **Add the request test to `tests/roadmap/stage/test_roadmap_stage_plan.py`.**: The existing request test and the `Registry places` test live there, and they build the request with a fake model client.
- **Keep the section text in `src/devops_cli/roadmap/stage/stage.py` and add no message constant.**: The `Registry places` section uses the same inline form, so the plan names no message file and adds no message text.

## Rejected alternatives

- **Say in `why` that `check_proposal` calls `read_change`.**: `src/devops_cli/roadmap/stage/stage_change.py:1204:proposal: StageProposal,` shows that the gate takes a proposal, and `src/devops_cli/roadmap/plan_check.py:507:proposal = read_change(change_files)` shows the caller of the reader.
- **Add the entries to `collect_context`.**: `src/devops_cli/roadmap/refine/refine.py:def collect_context` builds the context of both the stage job and the refine round, so stage-only entries would reach the refine request.
- **Create `plan_read.file_texts_at` to match the name of the issue.**: `openspec/changes/archive/2026-11-05-3430-read-the-default-tree-once-per-run/proposal.md:38:It finds no `file_texts_at` and no `base_specs_at`. The change uses the real names.` The reader that returns file texts is `files_at`.
- **Add a separate key to `StageRequest` instead of the context.**: The issue names the stage context, and `tests/roadmap/stage/test_roadmap_stage_plan.py:549:assert "### Registry places" in request["context"]` shows the request test reads the context field.
- **Test the request entry in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.**: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads the prompt text, not the request context, and the request test lives in `tests/roadmap/stage/test_roadmap_stage_plan.py`.
