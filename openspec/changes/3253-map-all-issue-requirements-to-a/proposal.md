# Proposal

## Why

The plan check maps only the acceptance criteria of an issue to task groups, so a plan that drops another requirement line passes. #3253 closes that gap.

## What Changes

- Add `RequirementLine` and `requirement_lines(body)` to `src/devops_cli/roadmap/stage/stage_criteria.py`: each bullet under a refined section, each backticked repository path and `devops` command, and each `Decision:` line, with the ID `REQ-001` in source order.
- Add `StageCoverage` and `coverage_problems` to `src/devops_cli/roadmap/stage/stage_criteria.py`: one problem for each unmapped ID that quotes its text, and one for each scenario whose `when` names only a person's intent.
- Add the `coverage` list to `StageProposal` and `StageSplit` in `src/devops_cli/roadmap/stage/stage_change.py`, the `COVERAGE` member of `ProposalGate`, and its line in `check_gates`.
- Add the `requirements` list to the stage request in `src/devops_cli/roadmap/stage/stage.py` and the `coverage` list to the split request.
- Render the coverage lines in `criteria_section` of `src/devops_cli/roadmap/stage/stage_change.py` and pass `coverage` to `_tasks_file` and to the split render of `src/devops_cli/roadmap/implement/implement_run.py`.
- Read the coverage lines of the `## Criteria` section back into `coverage` in `src/devops_cli/roadmap/plan_read.py`.
- Name the `coverage` key and the `REQ-` IDs in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`, so the #3210 prompt test passes.
- Add the messages of the new problems to `src/devops_cli/lang/en/messages.py`.
- Add the `coverage` gate to the replay in `src/devops_cli/roadmap/stage/stage_eval_gates.py` and the case of #3170 to `tests/fixtures/roadmap_eval/stage/`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage context lists each requirement line of the issue, The plan maps each requirement ID, The plan check refuses a vague scenario WHEN clause, The plan reader reads the coverage of the change folder
- `roadmap-stage-eval`: The golden set holds a case of a dropped caller

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_requirements.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/case.json`, `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/issue.txt`, `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/plan.json`, `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/facts.json`

## Feasibility

- The premise is confirmed at the staging commit. `probes` gives the line `The path `stage_criteria.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_criteria.py`. No commit in the history deleted or renamed it.` The module lives in `src/devops_cli/roadmap/stage/`, so the plan cites that path and the old one is no false premise.
- `probes` also gives the line `The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` The commit moved the file into the subpackage, so the plan cites the new path.
- `probes` also gives the line `The path `tests/roadmap/test_roadmap_stage_plan.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_plan.py`.` The test moved with the module, and the plan cites the new path.
- `read_file` on `src/devops_cli/roadmap/stage/stage_criteria.py` showed `def acceptance_criteria` and `def criterion_problems`, so the acceptance-criteria parse and its check are there and the new extraction and check join them.
- `read_file` on `src/devops_cli/roadmap/stage/stage_change.py` showed `class StageProposal` with `criteria: list[StageCriterion] = Field(default_factory=list)`, `class StageSplit` with the same list, `def check_gates` with `ProposalGate.CRITERIA: criterion_problems(`, and `def criteria_section`, so a new list, a new gate and the rendered lines follow the existing ones.
- `read_file` on `src/devops_cli/roadmap/plan_read.py` showed `def _criteria(text: str) -> list[StageCriterion]:` with `raise PlanReadError(_TASKS, MESSAGES.roadmap.plan_read_bad_criterion.format(text=line))`, so a coverage line in `## Criteria` must be read back or plan-check refuses the plan.
- `read_file` on `src/devops_cli/roadmap/stage/stage_eval_gates.py` showed `def _criteria_gate` with `if not plan.mapped: return []`, so the replay skips a recorded plan with no list and the new gate follows that form.
- `read_file` on `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` showed `assert sorted(bullets) == sorted(StageProposal.model_json_schema()["properties"])`, so the prompt needs a bullet for the new `coverage` key and the #3210 test then passes.
- `read_file` on `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` showed `assert report.judged() == (69, 306)` and `assert len(defects) == 74`, so the group that adds the case updates the pinned counts.
- `read_file` on `src/devops_cli/roadmap/stage/stage_change.py` showed `def _self_acceptance_problems` with the marks `StageProposal`, `content_problems` and `no problem`, so the behavior group that changes that file gives a group test that builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it.
- The plan changes `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_criteria.py` and `src/devops_cli/ai/tasks/roadmap_stage_change.md`, which `STAGE_EVAL_TRIGGER_PATHS` holds, so one group runs `uv run devops roadmap eval stage --replay` with the score before and after the change.
- `plan_stage` in `src/devops_cli/roadmap/stage/stage.py` needs a client of the model service to ask for the plan. `collect_context` needs a checkout of the repository at the staged commit. `open_pulls` needs a network to read the open pull requests of the repository.
- The first checks run against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirements.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and `uv run devops roadmap eval stage --replay`.

## Existing Tool Considered

markdown-it-py parses the issue body, and the change reuses it in `stage_criteria.py` for the extraction. Itsallcode/openfasttrace (GPL-3.0, maintained, last activity 2026-11-01) traces requirements to implementation and tests in a checkout, but it reads a specification file and code annotations, not the task groups of a plan against the lines of an issue. The change builds the mapping itself: about 45k tokens to build, 12k tokens a year to keep, 8k tokens to fix until stable, and about 24 hours.

## Dependencies

None.
