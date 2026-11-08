# Design

## Decisions

- **Enforce the attribute check in `check_proposal`, and not in the stage probe only.**: `check_proposal` returns a problem that the stage job sends back to the model once, so a reply that keeps the missing attribute cannot pass. A probe fact informs the model and refuses nothing.
- **Read the model text from the checkout at the staged commit, and not from `StagedTree`.**: `StagedTree` holds paths only. `git grep` finds the module of a named class at the commit, `git show` reads its text, and `ast` reads the annotated field names with no import. It also reads a module that does not import at the workstation.
- **Read only the classes that the plan names, and not every class under `src/`.**: `referenced_classes` gives the class names of the dotted references. One `git grep` and one `git show` for each class bound the cost of the check.
- **Pass the fields to `check_proposal` as a keyword-only map.**: The stage job has the checkout and the commit, so it builds the map. The replay reads no git, so `CaseFacts` records the map in the golden case and `PlanUnderTest` passes it. A call with no map judges no model field.
- **Require the module of the model in a group's `changes` when the attribute is missing.**: A changed path renders into the tasks and the impact of the change, so the step that reads the new field also updates the model. A read or a task text changes no file.
- **Use the existing `paths` gate and its `missing_path` defect type for the replay case.**: The rule runs in `check_proposal`, which is the `paths` gate. A defect that names the model module in `paths` needs no new gate and no new defect type.
- **Keep the one-return rule of `check_proposal` for the new problem.**: The stage job already returns a problem to the model once and stops the item on a second reply with the same gap, so the new problem needs no second path.

## Rejected alternatives

- **A probe fact only, with no gate.**: `src/devops_cli/roadmap/stage_change.py` returns the problems of `check_proposal` to the model and stops the item on the second reply. A probe fact enters the model input and refuses nothing, so a reply that keeps `PullStatus.labels` would pass.
- **Read the model text from `StagedTree`.**: `StagedTree.read` keeps the paths of `git ls-files` and no file text (`src/devops_cli/roadmap/stage_paths.py:79`). A check of a model field needs the text of the module and the commit.
- **Import the model module to read its fields.**: The stage job judges a commit, and a module of that commit need not import at the workstation, so an import would fail on a commit that the check must still judge.
- **A regular expression over the model source.**: `src/devops_cli/github/client.py` declares its fields as annotations under a class that inherits `BaseModel`, with aliases and defaults. A regular expression misses the class boundary and matches a field name in a docstring.
- **Scan every `.py` file under `src/` in one pass.**: `src/` holds thousands of files, so one `git show` for each file costs more than one for each class that the plan names.
- **A hardcoded check of `src/devops_cli/github/client.py` only.**: A hardcoded module misses a model of another module and needs an edit for each new model module.
