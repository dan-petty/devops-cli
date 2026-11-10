# Design

## Decisions

- **A group moves a module when a created module has the same name, or lies under the sub-package of the name prefix.**: `store.py` to `db/store.py` and `stage_probe.py` to `stage/probe.py` are the two moves that the plan rules of #3372 and #3373 describe. A created test, a created document or a created module of another name in the same folder is new work, and no module leaves its place.
- **Read the class of a file from `CONST_DOCS_INVENTORY`.**: The inventory already says which files a tool writes and which are records. A second list in the gate would drift from it.
- **Keep the gate for every other file.**: A caller, a test and a hand-written document that name a moved module still need a task group or an `unchanged` entry with a reason.

## Rejected alternatives

- **Ask the model to mark each of the hits unchanged with a reason.**: The log holds up to 560 hits for one item, and the files cannot be edited by a task group, so a reason for each is work with no value.
- **Skip the gate when the number of hits is large.**: A large move is the case that the gate was made for (#3373).
- **Drop `openspec/changes/archive/` only.**: The gate would still ask a plan to edit the proposal of another open change, and the plan rules forbid a task group to change a file of a change folder.
