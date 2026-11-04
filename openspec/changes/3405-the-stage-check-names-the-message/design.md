# Design

## Decisions

- **Read the task texts that render into `tasks.md` (test, implementation, documentation, verify, process) for a `MESSAGES.roadmap` name, and match the bare group with an optional dotted attribute.**: The example task names the bare group and adds no message file line, so a scan of dotted names only would miss it, and a scan of the whole reply would fire on a summary that mentions the catalog with no code change.
- **Name `src/devops_cli/lang/en/messages.py` in the problem text, and accept the plan when any group lists it in `changes`.**: The catalog of the roadmap messages is the file that defines `MESSAGES.roadmap`, so the file is the one path a task that names a message needs. The group that adds the problem text changes `messages.py` as well, because the project holds every output string in the catalog.
- **Widen the `missing_path` bullet in the verification prompt to a code change that needs a file that the plan does not change.**: The type today names only a file that does not exist, so a new line with a second meaning would contradict the first and leave the pass two definitions. One bullet that names both cases keeps the prompt and the validator on the same kinds and returns the plan once.
- **Add the new content cases to `tests/roadmap/test_roadmap_stage_plan.py`, and add the prompt case to `tests/roadmap/test_roadmap_stage_verify.py`.**: The stage plan tests already build plans and call the stage checks, so the content cases reuse their fixtures; the verify tests already read the verification prompt, so the prompt case sits beside them. `tests/roadmap/test_roadmap_stage_content.py`, which holds the other content cases, must keep passing.

## Rejected alternatives

- **Scan only dotted message names such as `MESSAGES.roadmap.foo`.**: The example of the issue, the plan of the pull request for #3343, names the bare `MESSAGES.roadmap` group and adds no message file line, so a dotted-only scan would accept it.
- **Type the defect `other` in the verification pass, as the pass did for that plan.**: The issue states that the stage comment named the finding, the draft stayed open, and a person had to edit the plan, so `other` does not return the plan.
- **Add a new defect type beside the nine that the prompt and the validator hold.**: No other type names a code change that needs a file the plan does not change, and a new type would need a matching change in the validator, so the change widens the existing `missing_path` type instead.
- **Leave the `missing_path` bullet as it is and add a second line for an unchanged file.**: The two lines would give the type two definitions, and a model that reads only the first would keep the plan in draft.
