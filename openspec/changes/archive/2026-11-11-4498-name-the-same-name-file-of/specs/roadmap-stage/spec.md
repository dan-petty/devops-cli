## ADDED Requirements

### Requirement: The stale test path problem names the same-name files
The problem of a test path that names no file of the commit SHALL end with the same hint as the missing-path message: the text of `stage_path_same_name` for the files of the staged tree with that file name, or the text of `stage_path_no_same_name` when no file has the name.

#### Scenario: One file has the same name
- **WHEN** a changed docstring names `tests/test_item_grounding.py` and the staged tree holds `tests/github/test_item_grounding.py`
- **THEN** the problem ends with the text of `stage_path_same_name` for `tests/github/test_item_grounding.py`

#### Scenario: No file has the same name
- **WHEN** a changed docstring names `tests/test_absent.py` and no file of the staged tree has the name `test_absent.py`
- **THEN** the problem ends with the text of `stage_path_no_same_name`
