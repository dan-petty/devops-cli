# Spec Delta

## ADDED Requirements

### Requirement: A refused verification command is a refused tool
The classifier SHALL give the class `refused_tool` to the text of a stop in which the step refused a verification command, for a program, an option, a shape or a length, whatever words the reason lists. The rule SHALL follow the message of the step. The default action of the class SHALL stay `wait`.

#### Scenario: A refused program
- **WHEN** a step refuses the verification command `curl http://example.com`, and the reason lists `mypy` and `ruff` among the allowed programs
- **THEN** the class is `refused_tool` and the action is `wait`

#### Scenario: A refused option and a refused shape
- **WHEN** a step refuses `! git grep -O name src/`, `! git grep -n name src/ | cat` or a command longer than 2000 characters
- **THEN** the class is `refused_tool` and the action is `wait`

#### Scenario: A command that ran and failed
- **WHEN** the stop reason says that `uv run mypy --strict -- a.py` exited with status 1
- **THEN** the class is `types`
