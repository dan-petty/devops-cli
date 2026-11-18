# Design

## Decisions

- **Instruct the planner to map whole-suite criteria to the completing group.**: Global, performance, or hermeticity criteria apply to the whole change or suite. Mapping these criteria to the task group that delivers or completes the suite satisfies criteria mapping without synthetic trailing groups.
- **Forbid docstring-only and instruction-only task groups.**: Explicitly instruct the model not to create task groups that only update docstrings or restate instructions. This prevents `group-no-files` failures and saves runner steps.
- **Update both change and split prompts.**: Both `roadmap_stage_change.md` and `roadmap_stage_split.md` govern task group creation and criteria mapping, so both prompts must state the rules.
- **Add the requirement to `roadmap-stage/task-groups`.**: That capability already specifies task group structure, kinds, files, and staging prompt instructions.

## Rejected alternatives

- **Loosen the group-no-files plan check.**: Groups that pack no repository files waste execution steps and resources in the runner. The plan check correctly detects empty groups; the prompt must avoid generating them.
- **Map whole-suite criteria to pending-person.**: Whole-suite criteria describe automated verification bounds that the implementation must satisfy, not manual person tasks.
