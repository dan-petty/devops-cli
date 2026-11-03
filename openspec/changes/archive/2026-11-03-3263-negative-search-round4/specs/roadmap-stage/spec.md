# Spec Delta

## MODIFIED Requirements

### Requirement: The paths of a negative search are checked against the staged commit
`check_proposal` SHALL read the paths of a `verify` command that is a negative search from the reader of the step, and SHALL refuse a path that is no file or folder of the staged commit and that no group up to its own creates. A path that ends in `/` SHALL be a folder. The path `.` SHALL not be judged. A glob SHALL be judged by the files that it matches.

#### Scenario: A folder that is not in the commit
- **WHEN** a group gives the `verify` command `! git grep -n hello scr/ testz/` and the commit has `src/` and `tests/` only
- **THEN** `check_proposal` returns a problem for `scr` and one for `testz`

#### Scenario: Folders of the commit and a folder that the plan creates
- **WHEN** a group gives the `verify` command `! git grep -n old_name src/ tests/`, `! git grep -n x -- .` or `! git grep -n x -- tests/newdir`, and the plan creates `tests/newdir/test_new.py`
- **THEN** `check_proposal` returns no problem about the paths

#### Scenario: A file with a trailing slash
- **WHEN** a group gives the `verify` command `! git grep -n devops README.md/` and `README.md` is a file of the commit
- **THEN** `check_proposal` returns a problem for `README.md`
