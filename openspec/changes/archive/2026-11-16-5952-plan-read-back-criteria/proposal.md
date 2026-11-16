# Proposal: #5952

## Why

Since #5851, the stage job reads each plan back before the push. From 2026-11-16 02:00Z to 06:40Z, 4 of 9 stage attempts failed with `RoadmapPlanReadBackError` (class `plan_unreadable`): #2202, #3655 and #3671 on `criteria`, and #3666 on `group 4: implementation`. The error names only the field, and no log, comment or record keeps the two values.

A reproduction with no model call takes the acceptance criteria of the three items from their bodies, renders them with `render_change` and reads them back with `read_change`:

- The text of each criterion reads back the same as a group entry with no reason and as a `pending-person` entry.
- A group entry with a `reason` reads back with no reason. The prompt asks for a string `reason` in each entry, so a model gives `""` or a sentence to a group entry. The line `Group <n>: <criterion>` holds no reason, so the reader gives `None`, and `file_facts` keeps the reason of the model. Each of the three items fails on `criteria` in this form, with `""` and with a sentence.
- A criterion with a line break, two spaces or U+FEFF reads back folded: the writer folds it on one line, and `StageCriterion` keeps the text of the model.
- A `behavior` or `manifest` group whose work names the command of the documents step (", and run `uv run devops docs generate`") reads back with its work cut at that command. When the group has a documents task, only `implementation` differs, as for #3666 group 4. `docs/TELEMETRY.md`, which #3666 changes, is a document that `devops docs generate` writes. No record keeps the reply of #3666, so the text of its group 4 is not known.

Closes #5952.

## What Changes

- `StageCriterion` folds `criterion` and `reason` with the fold of the writer (`one_line`, which moves from `stage_change.py` to `stage_criteria.py`), and an entry of a group keeps no reason. An entry then holds what its line of `## Criteria` holds.
- The plan reader takes the whole second task of a `behavior` or `manifest` group as its work. It cuts the documents step only from the end of a documents task, and only when the writer adds the step (`regenerates_documents`).
- `plan_read.read_back_differences` gives each fact that differs, the place of its first difference (an entry index, a field name, a character index) and the written and read values, masked (`mask_secrets`) and cut to 200 characters. `read_back_problems` gives the fact names from it.
- The stage job logs one line for each difference and puts the differences in the details of `RoadmapPlanReadBackError`. The message and the comment at the limit keep only the fact names, as #5214 decided.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: write, then read, keeps a group reason and a work that names the documents command; a read-back difference names its first place and both values.
- `roadmap-stage/criteria`: a criterion entry holds what its line holds.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/stage/test_roadmap_stage_failure_class.py`.
- Documents: `docs/roadmap/stage.md`.
- The schema of the stage reply and the prompts do not change.

## Feasibility

- The reproduction above runs with no model: `render_change` and `read_change` on the acceptance criteria of #2202, #3655 and #3671 from `devops gh api repos/dan-petty/devops-cli/issues/<n>`.
- The stage Job logs (`{namespace="devops", container="stage"}`) give only the field names: #2202, #3655 and #3671 on `criteria`, #3666 on `group 4: implementation`. A run of #2202 25 minutes before its failure staged a plan (#5941) whose criteria read back, so the failure depends on the reply.
- A `pending-person` line splits its criterion and its reason at a comma. A criterion that holds a comma and does not end with a full stop reads back cut. The criteria of the three items end with a full stop, so this form did not fail them. #5956 covers it.

## Existing Tool Considered

No library is added. `repr`, `mask_secrets` of the project and a scan for the first index cover the record of a difference. A diff library such as `deepdiff` gives every difference of a nested value, and the log line needs only the first one.
