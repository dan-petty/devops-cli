# Spec Delta

## MODIFIED Requirements

### Requirement: A plan run keeps its messages inside the context window
A plan run SHALL offer no tool to a request when the tokens of its messages, with a quarter of the context window of the `stage` task, reach the window. The model SHALL then give its plan. The tool answers SHALL NOT make a request longer than the window by more than the reply that was kept free.

#### Scenario: A model that reads a big file in every turn
- **WHEN** a plan run has a window of 12000 tokens and the model reads a file of 120 long lines in every turn
- **THEN** a request offers no tool before the budget of tool calls, no request passes the window, and the plan stages the item

#### Scenario: A run with no window
- **WHEN** a run is given no window
- **THEN** only the budget of tool calls takes the tools away

## ADDED Requirements

### Requirement: The stage job plans with the model of the stage task
The stage command and the stage round of the Service SHALL give the planner the model of the task `stage` as its toolbox model, and the call that splits the groups SHALL use the client of the task `stage`.

#### Scenario: The command asks for the stage model
- **WHEN** `devops roadmap stage --plan` plans an item
- **THEN** the command asks for the model of the task `stage`, and the planner offers its tools to that model

#### Scenario: A round asks for the stage model
- **WHEN** a round of the Service plans an item
- **THEN** the round asks for the model of the task `stage`
