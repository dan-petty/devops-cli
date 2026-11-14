# Tasks

## 1. Name the test modules of each cited function in the probe

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [ ] 1.1 Write `test_the_probe_names_the_test_module_of_a_cited_function` in `tests/roadmap/stage/test_roadmap_stage_probe.py` first: the fixture tracks `test_sample.py` in the tests folder with a call of `keep_comment`, and the probe of a body that cites `keep_comment` holds a line that names that test module. Also update `test_the_model_input_holds_the_probe_of_each_cited_path_and_identifier` in `tests/roadmap/stage/test_roadmap_stage_plan.py` for the new line that says that no test module names `keep`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 In `_Run` of `src/devops_cli/roadmap/stage/stage_probe.py`, add a cached listing that runs one `git grep -n -w -F -e <name>` at `self.sha` with `-- tests/` for the cited identifiers and maps each name to the sorted test module paths whose line holds it as a word; a non-zero exit gives no module, and a run with no cited identifier spends no command. `probe_premise` gives the run the cited identifiers before the loop. In `identifier`, append the line of `stage_probe_test_modules` after the definition lines, the line of `stage_probe_test_modules_none` when the map holds no module, and the line of `stage_probe_test_modules_bound` when no command is left. Add the three texts beside `stage_probe_defined` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 2. Send the test of a behavior group to the module of the changed function

Kind: behavior. Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 Write `test_the_prompts_name_the_test_module_of_a_changed_function` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` first: it loads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md` and asserts that each names `probes` as the source of the test module, and it loads `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md` and asserts that it names `references` and the test module that the answer lists
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 2.2 Add one sentence to the rule for the test of a behavior group in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and in `src/devops_cli/ai/tasks/roadmap_stage_split.md`: the `test` goes in the test module that `probes` names for the function whose behavior the group changes. Add one bullet to the `When to call them` list of `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`: call `references` for that function and write the test in a test module that the answer lists. Then run `uv run devops roadmap eval stage --replay` and compare the score before and after the prompt edit; the score must not fall
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## Criteria

- Group 2: The stage prompt asks the planner to call `references` for a changed function and to use the test module that the answer lists.
- Group 1: The stage context names the test modules that reference each function the issue cites.
- Group 2: A prompt rule test fails when either text is absent.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
