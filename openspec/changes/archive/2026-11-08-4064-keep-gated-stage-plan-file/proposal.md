# Proposal

## Why

#4064 asks that the stage job keeps the plan that passes the gates. Today a failed run drops the plan, and the next run explores the repository from the first tool call again. One plan used up to 1.5 million input tokens (#3880). `devops roadmap stage --plan` prints a plan and writes nothing, so `--confirm` plans the same item again.

The item record cannot hold the plan: it holds marks only. So this change keeps the plan as a local file, with a key of its input, and reads it back when the key is the same.

The hit rate is unmeasured. The live counter `devops_cli_roadmap_stage_total` showed 388 `failed`, 116 `staged` and 34 `returned` items in 7 days (the numbers of the issue). The 388 is an upper bound, because `failed` also counts a failed write and a plan staged with an open finding, and the AI token metrics have no task label. So this change adds a counter of hits, misses and writes, and a person reads the real rate after the merge. If the counter shows no hit after 14 days, a person decides to remove the file.

## What Changes

- A new module `src/devops_cli/roadmap/stage/stage_plan_record.py` holds `StagePlanRecord` (the key, the `StageProposal` that passed the gates, and the `StageRequest`), `plan_key`, `prompt_version`, `plan_record_path`, `read_plan_record` and `write_plan_record`. The file is `roadmap/stage/<owner>/<repo>/<number>.json` under the data directory, written with `write_json_file(..., atomic=True)` as `IntakeRecord` is. A file that cannot be read raises `RoadmapStageError` and names the file.
- The key is the sha256 of the item number, the hash of the title, the two hashes of `body_hashes` for the body, the model name of the task `stage`, the toolset name and the prompt version. The prompt version is the sha256 of the texts of `roadmap_stage_change.md`, `roadmap_stage_split.md` and the tools prompt of the toolset. The staged commit is no part of the key.
- `_Planner.plan` reads the file first. A file with the same key is a hit: the planner sends no request, runs the gates again on the current commit with the kept request (`_settle`), and runs the model review again. A file with another key is deleted at once. After `_gated` returns a change, the planner writes the file, before the review, so a failed review leaves it.
- `StageWriter` deletes the file when it stages the item. A failed write leaves it.
- `devops_cli_roadmap_stage_plan_record_total` (label `result`: `hit`, `miss`, `written`, 3 series) counts each use. `docs/TELEMETRY.md` lists it.
- `--plan` now writes one local file and makes no GitHub write. The help `stage_plan`, `docs/roadmap/stage.md` and the spec say so. The requirement "A stage plan writes nothing" is renamed "A stage plan makes no GitHub write".
- `plan_item` (the golden set) keeps no file.
- The change carries a spec delta: the command, its help, a file and a metric are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A stage plan makes no GitHub write (renamed from "A stage plan writes nothing"), A plan that passes the gates is kept as a file, A kept plan with the same key sends the planner no request, An unreadable plan file stops the item with its name, A staged item or a changed key deletes the plan file, Each use of the plan file counts by its result

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_plan_record.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/stage.md`, `docs/TELEMETRY.md`, `docs/CONFIGURATION.md` is unchanged (no setting changes)
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan_record.py` (new), `tests/roadmap/test_roadmap_command_help.py`

## Feasibility

I read the code at `origin/main` (bfe01926) and ran no model and no cluster command.

- The premise holds: nothing keeps a plan today. `git grep -n "stage_plan_record\|StagePlanRecord" -- src tests docs openspec` finds no match at the staging commit. The merged work this change builds on is in the tree: `StageRequest` (#4046, `src/devops_cli/roadmap/stage/stage_request.py`), the failure class (#4056) and the retry time (#4060). #4034 writes each item as it finishes and stores no plan.
- The planner flow allows a hit. `_Planner.plan` calls `_request`, then `_gated`, then `_verified` (`src/devops_cli/roadmap/stage/stage.py:907`). `StagedChange` is a frozen dataclass that holds `StageTarget`, `MeasuredGroup` and `RunTrace`, and only `_settle` builds it from a `StageProposal` and a `StageRequest` on the current tree (`stage.py:1116`). So the file keeps the two pydantic models and a hit calls `_settle` again. This keeps the gates on the current commit, as the issue asks, and keeps a dataclass with trace objects out of JSON.
- The atomic write exists: `write_json_file(path, data, indent=2, atomic=True)` is the writer of `IntakeRecord` (`src/devops_cli/roadmap/run.py:291`). The unreadable-file error has a model in `read_intake_record` (`run.py:272`).
- The key inputs exist. `body_hashes` returns the hash of the body outside the refine section and the hash of the section (`src/devops_cli/roadmap/body_hash.py:63`). The prompts are read with `load_task_prompt`: `_CHANGE_TASK` (`stage.py:677`), `SPLIT_TASK` (`stage_split.py:12`) and `_TOOLS_TASK` with `_EXTENDED_TOOLS_TASK` (`stage_toolbox.py:54`). The code has no prompt version today, so this change defines it as the hash of those texts, as the issue says.
- The directory exists in the Service. `service_state_dir()` is `<data dir>/roadmap` (`run.py:1158`), and the Service keeps that folder on the volume `roadmap-service-home` (`k8s/README.md`, item 11). So a rerun in the Service finds the file. A runner pod without that volume gets only misses; the counter shows it.
- Rollout rule: this change adds, removes, renames and tightens no setting, so the example and the live ConfigMap need no change. `RoadmapStageConfig` has `extra="ignore"` (`src/devops_cli/config/settings.py:901`, read from the code), so a stale key in a ConfigMap would be ignored and not refused. `tests/config/test_k8s_devops_runtime.py` already loads the example ConfigMap into Settings, and the verify step runs it.
- The `--plan` text moved: the help is `stage_plan` in `src/devops_cli/lang/en/help.py` and the page row is in `docs/roadmap/stage.md` (the issue says line 95; the row is now in the `Modes` table).
- Not proved, as the issue says: the hit rate. The counter of this change measures it after the merge.
- The test file named by the issue, `tests/roadmap/stage/test_roadmap_stage_plan_record.py`, and the test `stage_plan_help` in `tests/roadmap/test_roadmap_command_help.py` do not exist at the staging commit. The tests group of this change adds them.

## Existing Tool Considered

The need is a local file of a pydantic model with an atomic write and a hash key. The repository already has the parts: `write_json_file(..., atomic=True)`, pydantic `model_validate_json`, `body_hashes` and `load_task_prompt`, and `hashlib.sha256` of the standard library. An external cache library (for example `diskcache`) would add a dependency and a store format for one JSON file per item, and ADR 0008 plans to map these files to Argo artifacts one to one. So the change builds one small module on those parts, with no new dependency. Written cost, from the issue: about 70,000 tokens and 3.5 hours to build (the record, the key, the `--plan` contract, the help and documents, the counter and 8 tests), about 4,000 tokens each quarter to keep, and about 20,000 tokens and 1.5 hours to fix. The change deletes the help and page text "writes nothing" for `--plan`, and no other internal code.

## Dependencies

#4046, #4056 and #4060 are merged. Nothing blocks this change.
