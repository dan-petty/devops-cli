# Design

## Decisions

- **Put the listing of the referencing test cases in the premise probe and not in the stage context pack.**: The plan request already holds the probe lines, the probe already counts its commands and reports the bound, and the context pack of a step carries no test-case listing.
- **Run the pair listing after the paths, the class fields and the identifiers.**: The feasibility gate needs a path line, so a long listing must not use the commands that a path line needs.
- **Read each cited test module and each cited source file once with `git cat-file -p` and keep the text for the rest of the run.**: The pinned command set already holds `cat-file`, so the listing adds no command kind and no assertion of `test_every_command_reads_and_the_checkout_does_not_change` changes.
- **Name the test module and the source file, and not the cases, in the line that reports the reached bound.**: The probe cannot name a case without a command, and the bound is the reason it stopped; the pair is what the planner must read.
- **State the rule of the invalidated case in the planner prompt, with no validator over the plan's texts.**: The refinement of the issue rejected a validator over free text, and the prompt is the planner's only copy of a rule that has no machine form.
- **Assert the prompt rule in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and leave the snapshot of the rendered plan alone.**: That test holds the phrases that the prompt and `docs/roadmap/stage.md` must both keep, and the snapshot records the rendered change files, not the prompt.
- **Pair only the cited paths that the staging commit holds.**: A path that the commit lacks already has its missing line, and a pair over it would repeat that answer as an unlisted item.
- **Keep the listing inside the probe module and its messages, and add no field to a type of another module.**: The per-run state of the probe is private to `src/devops_cli/roadmap/stage/stage_probe.py`, and the other modules that hold a class of that name call only their own, so the listing needs no change outside the probe module and `src/devops_cli/lang/en/messages.py`.

## Rejected alternatives

- **Add a planner tool that lists the test cases of a module.**: `docs/roadmap/stage.md:41:The model plans with read-only tools.` fixes the toolset, and a tool call spends the budget of the plan run.
- **Raise `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` so that every pair is listed.**: `tests/roadmap/stage/test_roadmap_stage_probe.py:133:assert CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS == 10` pins the bound, and the bound keeps the inputs of a step inside its token budget.
- **Refuse a plan whose behavior group names an existing test module and no case.**: The group's `test` text always names the new case, so a gate over the texts cannot tell the new case from the invalidated one, and the refinement of the issue rejected a validator over free text.
- **Record the prompt rule in the snapshot of the rendered plan.**: `tests/roadmap/stage/test_roadmap_stage_plan.py:203:assert change.files == snapshot` shows that the snapshot holds `change.files`, the rendered change folder, so it holds no prompt text.
