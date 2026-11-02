# Proposal

## Why

The stage job plans an item without mapping its acceptance criteria to task groups, so about 10 of 37 plans of 2026-11-01 drop at least one criterion (#3019). No rule asks the model for the mapping and no check refuses a reply that leaves a criterion out.

## What Changes

- Add `StageCriterion` and `criterion_problems` in the new module `src/devops_cli/roadmap/stage_criteria.py`, and a `criteria` list (default empty) on `StageProposal` and `StageSplit` in `src/devops_cli/roadmap/stage_change.py`.
- An acceptance criterion is a top-level item of a list under a heading `Acceptance criteria` in the text of the issue body that a person wrote. The parser (`markdown-it-py`, already a dependency) cuts off the refine block first, because that block has its own heading in another form. A body with no such heading has no criterion.
- `check_proposal` takes the issue body as the keyword `issue_body` (default empty) and refuses a reply with an unmapped criterion. The job passes the whole `item.body`, not the part cut for the model. A problem quotes the exact text to copy, so the one retry can copy it.
- Render a `## Criteria` section in `tasks.md`, before `## Workflow follow-up`, with one line for each criterion and its group or `pending-person` and reason.
- A split moves the numbers of the groups, so the split request holds the `criteria` and the split reply gives them again; the job checks them after a split.
- State the rule in the prompts `roadmap_stage_change.md` and `roadmap_stage_split.md`.
- Add the `criteria` gate to the golden-set replay: `GateName.CRITERIA`, one entry in `GATES`, no entry in `PENDING_GATES`. The recorded plans have no `criteria` list, so the gate judges only a plan that has one. The 11 case files with a dropped-criterion defect change their gate from `pending` to `none`.
- Document the rule in `docs/ROADMAP_WORKFLOW.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Criteria mapping in the stage reply, Criteria section in tasks.md, criteria gate in the replay

## Impact

- Code: `src/devops_cli/roadmap/stage_criteria.py` (new), `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/lang/en/messages.py`
- Prompts and documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests and data: `tests/roadmap/test_roadmap_stage_criteria.py` (new), `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, and 11 `tests/fixtures/roadmap_eval/stage/*/case.json` files
- Callers of `check_proposal`: `src/devops_cli/roadmap/stage.py` and `src/devops_cli/roadmap/stage_eval_gates.py` pass `issue_body`; the new keyword has a default, so the other callers in `tests/roadmap/test_roadmap_stage_plan.py` keep working.

## Feasibility

- `git grep -n "def check_proposal" src/` finds `src/devops_cli/roadmap/stage_change.py`, and `git grep -n "check_proposal(" src/` finds its two callers, `src/devops_cli/roadmap/stage.py` and `src/devops_cli/roadmap/stage_eval_gates.py`. The gate checks specs and paths only, and `StageProposal` has no `criteria` field, so the premise of the issue holds.
- `git grep -n "def path_problems" src/` finds `src/devops_cli/roadmap/stage_paths.py`, the pattern of a pure function of the reply that `check_proposal` appends.
- The fixtures show three forms of list in an issue body. Counting `### Acceptance criteria` headings before the refine marker in `tests/fixtures/roadmap_eval/stage/*/issue.txt` gives 15 issues with the heading and 25 without it, and the refine block adds a second heading of another form. The parser therefore reads only the part before the block, and a body without the heading has no criterion.
- The golden set holds 12 defects of the type `criterion_dropped` in 11 case files, all with the gate `pending` (`git grep -c '"criterion_dropped"' tests/fixtures/roadmap_eval/stage`). The recorded `plan.json` files have no `criteria` key, so a gate that demands the list would refuse the three `good` plans. The gate skips a plan with no list.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_criteria.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_eval_gates.py` for the refusal, the section and the gate, and `uv run devops roadmap eval stage --replay` for the replay of the whole set.
- Not verified: whether an exact text match raises the rate of replies that fail the one retry. The prompt tells the model to copy the text, and a refusal quotes it. A run of the model on the live cases would show the rate; the pull request states that no such run was made.

## Existing Tool Considered

`markdown-it-py`, which the project already uses (`refine.py`, `step_files.py`), parses the issue body. No open, maintained tool maps criteria to task groups: the mapping is a rule of this job's reply schema, so the change builds the rule: a pydantic model, a pure function, a section of `tasks.md`, two prompt paragraphs and a gate. Written cost is about 130 lines of source (roughly 1500 tokens) and about 200 lines of tests to build, a few tokens per schema change to keep, and one focused session of 30 to 60 minutes to fix. The change deletes no internal code except the `PENDING_GATES` entry for #3019.
