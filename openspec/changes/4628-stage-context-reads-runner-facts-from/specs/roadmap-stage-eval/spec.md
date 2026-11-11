## REMOVED Requirements

### Requirement: The live run reads the runner facts in the checkout
**Reason**: The failure classes and the runner tools come from the installed modules, so no commit must hold `failure.py` or `runner_tools.py`, and the stage job no longer raises when a fact file is absent (#4628).
**Migration**: The requirement "The live run reads the image facts in the checkout" holds the fallback to the checkout for the runner image fact files, and states that a case or an item whose commit lacks a fact file reaches the model.

## ADDED Requirements

### Requirement: The live run reads the image facts in the checkout
The live run SHALL build the facts context of a case with the same builder as the stage job. It SHALL read each runner image fact file of that context at the commit of the case, and when the commit lacks the file, in the checkout of the run. The stage job SHALL read the staged commit only. A case or an item whose commit lacks a fact file SHALL still reach the model.

#### Scenario: A commit that lacks the fact files
- **WHEN** a case commit holds no `src/devops_cli/roadmap/failure.py` and no `src/devops_cli/roadmap/runner_tools.py`, the checkout holds both, and the issue text cites a failure word and a tool
- **THEN** the case reaches the model and does not end `refused`

#### Scenario: A checkout that lacks the module files too
- **WHEN** neither the commit nor the checkout holds `src/devops_cli/roadmap/failure.py` or `src/devops_cli/roadmap/runner_tools.py`, and the issue text cites a failure word and a tool
- **THEN** the case reaches the model and does not end `refused`

#### Scenario: The job plans an item whose commit lacks the module files
- **WHEN** the stage job plans an item and the staged commit holds neither `src/devops_cli/roadmap/failure.py` nor `src/devops_cli/roadmap/runner_tools.py`
- **THEN** the job makes a model call and raises no `RoadmapStageError`
