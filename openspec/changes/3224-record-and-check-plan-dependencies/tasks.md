# Tasks

## 1. Read the dependencies section back into the plan

Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_plan_read.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_plan_read.py`, add `test_the_reader_reads_the_dependencies`, which renders `make_stage_proposal(dependencies=["#3201: the check command"])` and asserts that `read_change` returns that list, and `test_a_plan_with_no_dependency_reads_as_no_entry`, which renders a plan with no dependency and asserts an empty list
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [ ] 1.2 Pass `dependencies=_bullets(_section(proposal_md, "Dependencies"))` in the `StageProposal` that `read_change` builds in `src/devops_cli/roadmap/plan_read.py`. The writer puts no bullet in the section when the list is empty, so an empty plan reads as an empty list with no second rule
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` passes

## 2. Read the issue numbers of the dependencies

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/support/builders.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`.

- [ ] 2.1 In `tests/roadmap/stage/test_roadmap_stage_form.py`, add `test_the_issue_form_gives_its_number`, which expects `[3201]` from the entries `#3201: the check command` and `an open pull request changes src/devops_cli/roadmap/plan_check.py`, and `test_an_entry_with_no_issue_form_is_skipped`, which expects an empty list from `a metric name and its other files`. In `tests/roadmap/stage/test_roadmap_stage_content.py`, add `test_the_plan_of_this_change_passes_the_content_rule`, which builds the plan's own `StageProposal` with `make_stage_proposal` and asserts that `content_problems` returns no problem for it
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` fails on the base
- [ ] 2.2 Add `_ISSUE_DEPENDENCY` and `issue_dependencies(dependencies: Sequence[str]) -> list[int]` to `src/devops_cli/roadmap/stage/stage_change.py`, beside `_overlap_problems`. The function matches `^#(?P<number>[0-9]+):` on each stripped entry and returns the numbers in order, and it skips an entry of another form. Run `uv run devops roadmap eval stage --replay` before the merge and state the score before and after the change
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` passes

## 3. Report an open issue dependency in plan-check

Reads: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_check.py`. Changes: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_check.py`.

- [ ] 3.1 In `tests/roadmap/test_roadmap_plan_check.py`, add `test_an_open_issue_dependency_is_reported`, whose plan lists `#3224: the dependency record` and whose fake client answers that issue 3224 is open, and assert one problem with the rule `issue-dependency` that names 3224. Add `test_a_dependency_that_is_not_open_is_no_problem` and `test_an_overlap_entry_is_no_issue_dependency`, which assert no `issue-dependency` problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` fails on the base
- [ ] 3.2 Add `_dependency_problems(proposal, root, reads, repo)` to `src/devops_cli/roadmap/plan_check.py`: for each number of `issue_dependencies(proposal.dependencies)` it reads `reads.get_issue(repo, number)` and appends one `PlanProblem` with the path of `proposal.md` in the change folder and the rule `issue-dependency` when the state is open. Call it from `plan_check` after `_gate_problems`. Add `plan_check_issue_dependency` and `plan_check_request_dependency_issue` to the roadmap messages in `src/devops_cli/lang/en/messages.py`, and list the dependency-issue read in `plan_check_requests`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` passes

## 4. Name the issue form in the planner prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 4.1 Add a sentence to the dependencies rule of the prompt: an entry that starts with `#<number>:` names an issue that must be delivered first, and the reason says why the issue comes first. Extend `test_the_prompt_states_the_dependencies_rule` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` to assert that the prompt holds `#<number>:`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 4.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` so the dependencies rule names the issue form
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
