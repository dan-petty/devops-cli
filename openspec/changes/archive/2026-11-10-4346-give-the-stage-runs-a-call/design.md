# Design

## Decisions

- **A notice on the tool answers, with the tools still on.**: The model reads the notice in the place where it decides on the next call. A hard stop at 40 calls would fail a run that needs a few more checks, and the window limit stays the hard stop.
- **Two budgets, 40 and 60.**: A review run checks each path and each premise of a plan, so it needs more calls than a plan run. The numbers sit above the middle of the runs of 7 days (33 and 53) and near their 90th percentile (43), so the notice reaches only the long runs.
- **The prompt names the advised calls, 30 and 40, and the notice follows 10 and 20 calls later.**: The advice sets the aim, and the notice is the reminder for a run that went past it.
- **Count in `StageTools`, restart in `ToolboxClient`.**: The tools know their calls. The client knows when a run starts and which schema the run answers.
- **A request with `problem` reads little.**: A gate return took 4 calls in the live trace, and a repair round took 49 although the findings name the paths to check.

## Rejected alternatives

- **A hard limit of 40 calls.**: It ends a run that needs more, and the forced reply then holds placeholders (#3880).
- **A guard that answers a repeated call with the earlier answer.**: Only 3% of the read lines in the live plan run were read before, so the guard has almost nothing to save.
- **A shorter tool answer.**: The caps are in #4218 and #4341, and a shorter answer makes the model read more.
