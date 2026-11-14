## MODIFIED Requirements

### Requirement: The turn for a failed static check changes only the files of the step
The turn for a failed static check SHALL change no file except `tasks.md`, the files that the step had changed before the turn, and a file whose content the turn restores to its content at `keeper.base`. The step SHALL check this with git, and SHALL stop with a reason that names the other paths when the turn changed any. A file that the turn deletes and that exists at `keeper.base` SHALL stop the step.

#### Scenario: The turn changes a file that the step did not change
- **WHEN** the model changes `src/other.py` in the extra turn, the step had not changed it, and its content differs from `keeper.base`
- **THEN** the step reports stopped with the reason that names `src/other.py`, makes no commit and resets the checkout

#### Scenario: The turn changes a file that the step changed
- **WHEN** the model changes `src/sample.py` in the extra turn, and the step had changed it
- **THEN** the step checks all exit checks again and does not stop for the change

#### Scenario: The turn restores a file to the base content
- **WHEN** the step changed `src/sample.py`, and the extra turn writes the content that the file has at `keeper.base`
- **THEN** `_foreign_change` returns None and the step continues with the exit checks

#### Scenario: The turn deletes a file of the base
- **WHEN** the extra turn deletes a file outside the allowed set that exists at `keeper.base`
- **THEN** the step stops with a reason that names the deleted file
