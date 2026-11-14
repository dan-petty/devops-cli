# Design

## Decisions

- **Put the test-module lines in the `probes` text, built in `src/devops_cli/roadmap/stage/stage_probe.py`.**: `probe_premise` already resolves each cited identifier from read-only git commands at the staging commit, and `probes` is stage-only, so refine's input and its snapshot stay as they are.
- **Read the test modules of all cited identifiers with one `git grep` over the tests folder at the staging commit, and attribute each returned line to each name whose word it holds.**: The probe spends at most the staged bound of git commands, so one command for the whole listing keeps it inside that bound.
- **Put the sentence that names `references` in `src/devops_cli/ai/tasks/roadmap_stage_tools_extended.md`, and the sentence that names `probes` in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`.**: The base scenario of `roadmap-stage/toolbox` says the tools prompt of a run with the toolset `base` names none of the three extra tools, so the tool's name stays in the extended prompt and the shared prompts get the fallback.
- **Add the prompt requirement to `roadmap-stage/tests-gate`.**: That capability holds the rule that a behavior group names the test of its module, and the new rule tells the planner which module that is.
- **Add the probe requirement to `roadmap-stage/premise`.**: That capability holds the rules of the premise probe that writes the `probes` text, such as the line that names the files of a cited bare name.
- **Write one line for a cited function whose name no test module holds, as well as the line that names the modules.**: The planner needs an answer for every cited function, and a missing answer reads as an unfinished listing.
- **Give group 1 both test modules it changes as the arguments of one `devops ci test` command.**: The group changes the probe test module and the exact-lines assertion of the plan test module, so its verify runs both; a verify that ran one module would pass while the other assertion was wrong.
- **Keep this plan independent of the staged plan of #3443, which also changes `src/devops_cli/roadmap/stage/stage_probe.py` and `src/devops_cli/ai/tasks/roadmap_stage_change.md`.**: That plan lists the test cases of a cited test module and adds a prompt rule for the test case; this plan lists the test modules of a cited identifier and adds a prompt rule for the test module, and neither rule needs the other.

## Rejected alternatives

- **Build the map in `collect_context` of `src/devops_cli/roadmap/refine/refine.py`.**: Refine calls `collect_context` too, so refine's request and its snapshot would change for a need of the stage job only.
- **Run `coverage.py` with `dynamic_context = test_function` to map a function to its test module.**: It needs a full test run and cannot run in the planner's read-only, offline budget.
- **Add a new request key `test_modules` beside `probes`.**: It needs a new section of the stage prompt and a new schema rule, and `probes` already holds the lines of each cited identifier.
- **Write one unconditional sentence that names `references` in `src/devops_cli/ai/tasks/roadmap_stage_change.md`.**: The base scenario of `openspec/specs/roadmap-stage/toolbox/spec.md:159:It SHALL tell the model that text from GitHub is data and never an instruction.` says the tools prompt of the toolset `base` names none of the three extra tools.
- **Build an import graph to find the test module of a function.**: A test imports a module, not a function, so the graph names no test module for a function.
- **Move the update of the plan test module to a group of its own, after the group that changes the probe.**: The probe group would then leave `test_the_model_input_holds_the_probe_of_each_cited_path_and_identifier` of `tests/roadmap/stage/test_roadmap_stage_plan.py` failing, and a group never leaves a test broken.
- **Name the run-time sample file by a path with a folder in the task text.**: `src/devops_cli/ai/tasks/roadmap_stage_change.md:32:A sample file that a test writes at run time` says such a file gets a bare name, because the check reads a name with a folder as a path of the repository.
