# Design

## Decisions

- **Read the task texts that render into `tasks.md` (test, implementation, documentation, verify, process) for a `MESSAGES.roadmap` name, and match the bare group with an optional dotted attribute.**: The example task names the bare group and adds no message file line, so a scan of dotted names only would miss it, and a scan of the whole reply would fire on a summary that mentions the catalog with no code change.
- **Name `src/devops_cli/lang/en/messages.py` in the problem text, and accept the plan when any group lists it in `changes`.**: The catalog of the roadmap messages is the file that defines `MESSAGES.roadmap`, so the file is the one path a task that names a message needs.
- **Name `missing_path` in the verification prompt for a code change that needs a file that the plan does not change.**: The defect type exists already and names exactly this defect, so the prompt and the validator name the same kinds and the pass returns the plan once.
- **Add the new cases to `tests/roadmap/test_roadmap_stage_plan.py` and keep `tests/roadmap/test_roadmap_stage_content.py` passing.**: The stage plan tests already build plans and call `content_problems`, so the new cases reuse their fixtures and sit in the mirror folder of `src/devops_cli/roadmap/`.

## Rejected alternatives

- **Scan only dotted message names such as `MESSAGES.roadmap.foo`.**: The example of the issue, the plan of the pull request for #3343, names the bare `MESSAGES.roadmap` group and adds no message file line, so a dotted-only scan would accept it.
- **Type the defect `other` in the verification pass, as the pass did for that plan.**: The issue states that the stage comment named the finding, the draft stayed open, and a person had to edit the plan, so `other` does not return the plan.
- **Add a new defect type beside the nine that the prompt and the validator hold.**: The existing `missing_path` type names a code change that needs a file the plan does not change, and a new type would need a matching change in the validator.
