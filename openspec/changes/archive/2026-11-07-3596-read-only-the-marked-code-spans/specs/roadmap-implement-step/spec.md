## MODIFIED Requirements

### Requirement: The verification commands of a group are the code spans of its Verification lines
The verification commands of a group SHALL be the code spans of the `Verification:` lines of its tasks that start with `$ `, with the mark removed, each one once, in the order of the file. Every other code span of such a line SHALL be prose. The step SHALL run each command as a list of words, never through a shell, and SHALL stop with the reason when the first word is not a program of the verification list or the `!` of a negative search in the fixed shape.

#### Scenario: Two lines name one command
- **WHEN** two tasks of the group name `$ uv run devops ci test tests/test_sample.py` and the second names `$ uv run devops docs check` as well
- **THEN** the step runs `uv run devops ci test tests/test_sample.py` once and `uv run devops docs check` once, in that order

#### Scenario: A prose code span beside a marked command
- **WHEN** a task holds a `Verification:` line with the code span `tagged_image` and the code span `$ pytest tests/roadmap/test_step_files.py`
- **THEN** the commands of the group are `pytest tests/roadmap/test_step_files.py` only

#### Scenario: A line with no mark
- **WHEN** a task holds a `Verification:` line with the code span `pytest tests/roadmap/test_step_files.py` and no mark
- **THEN** the group has no command from that line

#### Scenario: A marked command that the step refuses
- **WHEN** a task holds the code span `$ nosuchprogram --version` on its `Verification:` line
- **THEN** the step stops with a reason that names `nosuchprogram` as a program that is not in the allowed list
