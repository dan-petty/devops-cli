## ADDED Requirements

### Requirement: The live run reads the runner facts in the checkout
The live run SHALL build the facts context of a case with the same builder as the stage job. It SHALL read each source file of that context at the commit of the case, and when the commit lacks the file, in the checkout of the run. The stage job SHALL read the staged commit only. A file that neither the commit nor the checkout holds SHALL end the case `refused` with the path.

#### Scenario: A commit that lacks the fact files
- **WHEN** a case commit holds no `src/devops_cli/roadmap/failure.py` and no `src/devops_cli/roadmap/runner_tools.py`, the checkout holds both, and the issue text cites a failure word and a tool
- **THEN** the case reaches the model and does not end `refused`

#### Scenario: A file that the checkout lacks too
- **WHEN** neither the commit nor the checkout holds `src/devops_cli/roadmap/runner_tools.py`
- **THEN** the case ends `refused` and the reason names `src/devops_cli/roadmap/runner_tools.py`

#### Scenario: The job keeps its error
- **WHEN** the stage job plans an item and the staged commit lacks `src/devops_cli/roadmap/failure.py`
- **THEN** the job raises `RoadmapStageError` and makes no model call
