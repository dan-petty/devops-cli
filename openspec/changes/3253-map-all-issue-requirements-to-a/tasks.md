# Tasks

## 1. Extract the requirement lines of the issue

Reads: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`. Changes: `src/devops_cli/roadmap/stage/stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_requirements.py` (new).

- [ ] 1.1 Write `tests/roadmap/stage/test_roadmap_stage_requirements.py` with an issue body whose bullet under a refined section names `devops pr ready`, whose text holds a backticked path, and whose text holds a `Decision:` line, and assert that `requirement_lines` returns the IDs `REQ-001` to `REQ-003` with the kinds `command`, `path` and `decision`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirements.py` fails on the base
- [ ] 1.2 Add `RequirementLine` with the keys `id`, `kind`, `text` and `source_line`, and `requirement_lines(body)` to `src/devops_cli/roadmap/stage/stage_criteria.py`. The function cuts the refine block with `_without_refine_block`, reads the bullets under the headings of the remaining sections, the backticked repository paths and `devops` commands of the text, and each line that starts with `Decision:`, in source order, and skips the items of the acceptance-criteria list. The ID is `REQ-` and the number of the entry from 1, padded to three digits
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirements.py` passes

## 2. Refuse a plan that leaves a requirement out

Reads: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_requirements.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add `test_a_plan_that_drops_a_named_caller_is_refused_with_the_caller` and `test_a_plan_that_maps_every_requirement_passes` to `tests/roadmap/stage/test_roadmap_stage_requirements.py`, and add `test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirements.py tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Add `StageCoverage` with the keys `id`, `group` and `reason` and the validator of `StageCriterion`, and `coverage_problems(coverage, issue_body, group_count)` that returns one problem for each requirement ID with no entry, quoting the text of the requirement, one for an entry whose group the plan does not have, and one for each scenario whose `when` holds a phrase of a person's intent (`says so`, `decides`, `wants`, `approves`) and no backticked literal. Add `coverage: list[StageCoverage] = Field(default_factory=list)` to `StageProposal` and `StageSplit`, the member `COVERAGE = "coverage"` to `ProposalGate`, and the line of `check_gates` that calls `coverage_problems`. Add the messages of the new problems to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_requirements.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 3. Name the coverage key in the prompt and the request

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add a `- `coverage`:` bullet to the reply keys of `src/devops_cli/ai/tasks/roadmap_stage_change.md` that names the keys `id`, `group` and `reason`, the IDs `REQ-001`, and the rule that every ID of the `requirements` list of the request has one entry. Add the sentence that names the `requirements` list to the paragraph that describes the request. Name the `coverage` list of `StageSplit` in `src/devops_cli/ai/tasks/roadmap_stage_split.md`. Add the `requirements` list to `_request` in `src/devops_cli/roadmap/stage/stage.py` and the `coverage` list to the request of the split. Add `StageCoverage` to the models of `test_each_list_of_keys_of_the_reply_is_the_fields_of_a_model` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 3.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`
  - Verification: `$ uv run devops ci docs` passes

## 4. Render and read the coverage of a plan

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/test_roadmap_plan_read.py`.

- [ ] 4.1 Add a test to `tests/roadmap/test_roadmap_plan_read.py` that reads a change folder whose `## Criteria` section holds the line `REQ-001: group 2`, and asserts that the plan holds one coverage entry with the ID `REQ-001` and the group 2
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/stage/test_roadmap_stage_criteria.py` fails on the base
- [ ] 4.2 Render one line for each coverage entry in `criteria_section` of `src/devops_cli/roadmap/stage/stage_change.py`: `REQ-001: group 2`, or `REQ-002: pending-person, <reason>`. Give it a `coverage` parameter and pass `proposal.coverage` to `_tasks_file`, and pass `split.coverage` at the split render of `src/devops_cli/roadmap/implement/implement_run.py`. Read a bullet that starts with `REQ-` in a new `_coverage` of `src/devops_cli/roadmap/plan_read.py` into a `StageCoverage`, skip those lines in `_criteria`, and give the read plan the `coverage` list. Add the message texts of the new lines to `src/devops_cli/lang/en/messages.py`. Add the test of the rendered line to `tests/roadmap/stage/test_roadmap_stage_criteria.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

## 5. Add the coverage gate and the dropped caller case

Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3174-a-plan-with-a-placeholder-group/case.json`, `tests/fixtures/roadmap_eval/stage/3174-a-plan-with-a-placeholder-group/plan.json`, `tests/fixtures/roadmap_eval/stage/3174-a-plan-with-a-placeholder-group/issue.txt`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/case.json` (new), `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/facts.json` (new).

- [ ] 5.1 Add `test_the_coverage_gate_refuses_the_dropped_caller` to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, which replays the case of #3170 and asserts that the `coverage` gate returns one problem that quotes `devops pr ready`, and update the pinned counts that the new case moves
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 5.2 Add the member `COVERAGE = "coverage"` to `GateName` and `REQUIREMENT_DROPPED = "requirement_dropped"` to `DefectType` in `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Add a `coverage_mapped` field to `PlanUnderTest` and the `_coverage_gate` of `src/devops_cli/roadmap/stage/stage_eval_gates.py`, which returns no problem for a recorded plan with no `coverage` key, and add its `Gate` to `GATES`. Parse the `coverage` list of a case in `PlanUnderTest.of_case`. Add the case directory `tests/fixtures/roadmap_eval/stage/3170-the-plan-drops-a-caller-the-issue/`: its issue names `devops pr ready` in a bullet under a refined section, and its plan holds a `coverage` list with no entry for that caller and one defect of the type `requirement_dropped`, the gate `coverage` and the message `devops pr ready`. Update the pinned counts of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 6. Measure the replay before and after the change

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 6.1 Run `uv run devops roadmap eval stage --replay` on the base commit and on the change with the same model, and write the score before and after the change into the proposal of the change. Edit `docs/ROADMAP_WORKFLOW.md` to name the `coverage` gate with the other gates of the plan check
  - Verification: `$ uv run devops roadmap eval stage --replay` passes
- [ ] 6.2 Edit `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test shows that a plan that omits a named caller of the issue is refused with the caller named.
- Group 2: A test shows that a plan that maps every line passes.
- Group 3: The extraction and mapping are in the same module as the acceptance-criteria code, and the prompt is updated (#3210 test passes).
- Group 5: A replay case from #3170 or #3169 is in the golden set.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
