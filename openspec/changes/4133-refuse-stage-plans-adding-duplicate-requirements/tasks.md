# Tasks

## 1. Read the requirements of the active changes

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_specs.py`, `src/devops_cli/openspec/overlap.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, `tests/roadmap/stage/test_stage_jev_shadow.py`. Changes: `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_specs.py`.
Adds: `ActiveRequirement`, `read_active_requirements`

- [ ] 1.1 `tests/roadmap/stage/test_roadmap_stage_specs.py`: `test_an_active_change_gives_its_requirement_and_scenarios` writes a checkout whose delta file for the capability `alpha` modifies a requirement that holds one scenario, and asserts that `read_active_requirements` names the change, the requirement and the scenario; `test_a_removed_requirement_of_a_change_is_no_candidate` asserts that a section `## REMOVED Requirements` gives no entry
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py` fails on the base
- [ ] 1.2 Write the test first in `tests/roadmap/stage/test_roadmap_stage_specs.py`. Then add `ActiveRequirement` and `read_active_requirements` to `src/devops_cli/roadmap/stage/stage_specs.py`: walk the folders under the changes directory besides the archive, read the delta of the capability at its own spec file in that folder, and take the requirement name and the scenario names of each requirement of the added and the modified sections with the pattern of the module for a requirement heading and for a scenario heading. Leave out the removed section and a change that holds no delta for the capability, and sort the change names so that the answer is the same on each run
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py` passes

## 2. List the scenarios and the active changes in the spec tool

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`, `tests/support/fakes/openspec.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_tools.py`. Changes: `src/devops_cli/roadmap/stage/stage_tools.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`.
Adds: `_requirement_summary`, `_active_requirement_lines`

- [ ] 2.1 `tests/roadmap/stage/test_roadmap_stage_tools.py`: `test_the_spec_tool_lists_the_scenario_of_each_requirement` covers the scenario `A capability`, with a fake OpenSpec answer that holds two requirements of one scenario each, and asserts that the answer of `read_spec` names each requirement with its scenario; `test_the_spec_tool_lists_the_requirements_of_the_active_changes` covers `An active change modifies one requirement` and `A removed requirement is no candidate`, and asserts that the answer of `read_spec` names the change, the requirement and its scenario, and no requirement of a change that removes one. The tests `test_repo_map_shows_a_line_for_each_file_and_says_when_files_are_left_out` and `test_repo_map_cuts_a_long_line_and_never_a_line_in_the_middle_of_the_answer` cover the scenario `A directory with more files than the limit` of `repo_map`, and `test_read_spec_returns_the_whole_text_of_one_requirement`, `test_read_spec_gives_the_purpose_of_a_capability_with_no_requirement` and `test_read_spec_without_the_tool_says_so` cover the other scenarios of `read_spec`; they pass on the base and stay green
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` fails on the base
- [ ] 2.2 Write the test first in `tests/roadmap/stage/test_roadmap_stage_tools.py`. Then change `read_spec` of `src/devops_cli/roadmap/stage/stage_tools.py`: list each requirement of the capability through a new `_requirement_summary`, which appends the name of each of its scenarios from the OpenSpec JSON, and append the lines of a new `_active_requirement_lines` over `read_active_requirements(self.source, capability)`. State the answer in the docstring of the tool, and keep the answer inside the cap so that a long spec is cut
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` passes

## 3. Tell the planner to name the active change

Kind: other. Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add the rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: read the requirements of each capability that the plan changes with `read_spec` before adding a requirement, and name the active change as a blocker in `dependencies` when that change already adds or modifies the requirement whose behavior the plan needs. Add `test_the_prompt_names_the_active_change_as_a_blocker` to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, which asserts that the rendered prompt holds the rule. Run the live score `uv run devops roadmap eval stage --limit 5` and record the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 3.2 Edit `docs/roadmap/stage.md` to state that the spec tool lists the scenario of each requirement and the requirements of the active changes, and that the planner names the active change as a blocker
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
