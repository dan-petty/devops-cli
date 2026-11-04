# Design

## Decisions

- **One message names both the `creates` list and the ` (new)` mark, instead of a parameter that selects one form.**: `path_problems` serves the stage reply and the change folder from one rule set, and either reader can use either form, so one text needs no extra parameter at each caller.
- **The same-name hint stays at the end of the message, after the two forms.**: The hint names the tracked file of the same name, which is often the fastest fix, and it states that no file has the name when that is the case.
- **The message of a path that a later group creates stays unchanged.**: That message names the group that creates the path, which is a complete answer, and the two forms would add nothing to it.
- **The docstring of `stage_paths.py` names both readers.**: A reader of the module then sees why one message holds two forms.

## Rejected alternatives

- **A parameter of `path_problems` that selects the message form for each caller.**: The context lists four callers of `path_problems` (`implement_run.py`, `stage.py`, `stage_change.py`, `stage_paths.py`), and each would set a parameter for a text that the reader of either file can follow.
- **Replace the same-name hint with the two forms.**: `stage_path_same_name` names the tracked file of the same name, and dropping it removes the list of files that the reader most often wants, so the two forms join the hint instead.
