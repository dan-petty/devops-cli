# Design

## Decisions

- **Enforce the attribute check in `check_proposal`, and not in the stage probe only.**: `check_proposal` returns a problem that the stage job sends back to the model once, so a reply that keeps the missing attribute cannot pass. A probe fact informs the model and refuses nothing.
- **Read the models with `ast` from the source of the staged commit.**: `StagedTree` holds the file text of the staged commit. `ast` reads the annotated field names of a class with no import, so a module that does not import at the workstation still gives its fields.
- **Scan every Pydantic model class under `src/`, not one hardcoded module.**: The stage planner reads client models of several modules. A scan by class name covers them all and needs no edit for each new model module.
- **Require the module of the model in a group's `changes` when the attribute is missing.**: A changed path renders into the tasks and the impact of the change, so the step that reads the new field also updates the model. A read or a task text changes no file.
- **Keep the one-return rule of `check_proposal` for the new problem.**: The stage job already returns a problem to the model once and stops the item on a second reply with the same gap, so the new problem needs no second path.

## Rejected alternatives

- **A probe fact only, with no gate.**: `src/devops_cli/roadmap/stage_change.py` returns the problems of `check_proposal` to the model and stops the item on the second reply. A probe fact enters the model input and refuses nothing, so a reply that keeps `PullStatus.labels` would pass.
- **Import the model module to read its fields.**: `src/devops_cli/roadmap/stage_change.py` works on the `StagedTree` of the staged commit, which holds file text. A module of that tree need not import at the workstation, so an import would fail on a tree that the check must still judge.
- **A regular expression over the model source.**: `src/devops_cli/github/client.py` declares its fields as annotations under a class that inherits `BaseModel`, with aliases and defaults. A regular expression misses the class boundary and matches a field name in a docstring.
- **A hardcoded check of `src/devops_cli/github/client.py` only.**: `src/devops_cli/roadmap/stage_change.py` reads every path of the staged tree. A hardcoded module misses a model of another module and needs an edit for each new one.
