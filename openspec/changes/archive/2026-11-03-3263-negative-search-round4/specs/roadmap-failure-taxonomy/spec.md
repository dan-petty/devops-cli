# Spec Delta

## MODIFIED Requirements

### Requirement: A refused verification command is a refused tool
The classifier SHALL give the class `refused_tool` to the text of a stop that starts with the message in which the step refused a verification command, for a program, an option, a shape or a length. It SHALL read this rule before the rules for the other causes, whatever words the command or the reason holds. The rule SHALL follow the message of the step. The default action of the class SHALL stay `wait`.

#### Scenario: A refused program
- **WHEN** a step refuses the verification command `curl http://example.com`, and the reason lists `mypy` and `ruff` among the allowed programs
- **THEN** the class is `refused_tool` and the action is `wait`

#### Scenario: A refused option and a refused shape
- **WHEN** a step refuses `! git grep -O name src/`, `! git grep -n name src/ | cat` or a command longer than 2000 characters
- **THEN** the class is `refused_tool` and the action is `wait`

#### Scenario: A command that ran and failed
- **WHEN** the stop reason says that `uv run mypy --strict -- a.py` exited with status 1
- **THEN** the class is `types`

#### Scenario: A command with the words of another cause
- **WHEN** a step refuses `python -m pytest tests/roadmap/test_rate_limit.py`, or a search for `timed out`, `out of memory` or `merge conflict`
- **THEN** the class is `refused_tool` and the action is `wait`
