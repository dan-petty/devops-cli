# Design

## Decisions

- **Convert the pydantic error of a task group in the reader, where the group is built.**: The reader owns its error type, and the command and the implement round catch only `PlanReadError`. The group call ran outside the `try` of `read_change`, so the conversion sits at the group call and names the group.
- **Give the error the path `tasks.md` and the title of the group, with the pydantic problems on one line.**: A person needs the file and the group, and a plain line has no trace and no link.
- **Judge each code span of each `Verification:` line with `verification_problem`.**: The step runs every span of every task, and the stage gate and the step share this function, so the reader refuses no span that the step runs and accepts no span that it refuses.
- **Drop the `skip_specs` message by its exact text, and keep every other issue.**: OpenSpec gives the message for a valid change that sets `skip_specs`. Another INFO issue can be a delta that `openspec archive` refuses. A changed text of OpenSpec makes the message a problem again, which is the safe side, and a live test with the pinned tool holds the text.
- **Add one sentence to the stage prompt for a sample file, and leave the path rule to #3492.**: `stage_paths.py` reads a word with no folder as no path, so a bare name is the form that the check accepts.

## Rejected alternatives

- **Catch `ValidationError` in `plan_check`.**: The command is the only caller today, but the implement round will read plans too, and the reader must own its error type.
- **Exempt every INFO issue of OpenSpec.**: One INFO issue can be a delta that `openspec archive` refuses, as `docs/ROADMAP_WORKFLOW.md` and the spec of the stage job state.
- **Exempt no INFO issue.**: The stage job then refuses each valid plan that sets `skip_specs`.
- **Judge the first span of the first task only.**: It accepts the `helm template` span of a later task, which the step refuses.
- **Reject sample paths in the reader.**: That needs the rewrite of the path rule that #3492 owns.
