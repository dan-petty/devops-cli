# roadmap-plan-amendment Specification Delta

## ADDED Requirements

### Requirement: Plan request accepts add_path
`PlanRequest` SHALL accept `kind` `add_path` with `new` set to a repository path and `header` set to `Changes` or `Reads`.

#### Scenario: Parse an add_path request
- **WHEN** a step message ends with a `plan-request` fence whose JSON sets `kind` to `add_path`, `group` to 1, `new` to `src/app/constants.py` and `header` to `Reads`
- **THEN** `parse_request` returns a `PlanRequest` whose `kind` is `add_path` and whose `header` is `Reads`

### Requirement: Added path exists in the tree
The job MUST refuse an `add_path` request when `new` is not in `tree.files`.

#### Scenario: Refuse an absent path
- **WHEN** `new` is `src/app/missing.py` and `tree.files` does not hold that path
- **THEN** `judge` returns `Refused` with the message `implement_amend_refused_path_status`

### Requirement: Added path is outside openspec
The job MUST refuse an `add_path` request when `new` sits under `openspec/`.

#### Scenario: Refuse a path under openspec
- **WHEN** `new` is `openspec/changes/4099-bounded-path/tasks.md`
- **THEN** `judge` returns `Refused` with the message `implement_amend_refused_path_status`

### Requirement: Added path joins the named header line
The job MUST append the backticked `new` path to the `Changes:` or `Reads:` line that `header` names, and MUST leave every other line of the group unchanged.

#### Scenario: Append a path to the Reads line
- **WHEN** group 1 has a `Reads:` line that lists `src/app/a.py` and the request sets `header` to `Reads` and `new` to `src/app/constants.py`
- **THEN** the `Reads:` line lists `src/app/a.py` and `src/app/constants.py`, separated by `, `

### Requirement: Header line must exist
The job MUST refuse an `add_path` request when the group has no line for the `header` that the request names.

#### Scenario: Refuse a missing header line
- **WHEN** group 1 has no `Reads:` line and the request sets `header` to `Reads`
- **THEN** `judge` returns `Refused` with the message `implement_amend_refused_path_status`

### Requirement: Refuse a path that the group already holds
The job MUST refuse an `add_path` request when the group text already holds `new` in a code span.

#### Scenario: Refuse a duplicate path
- **WHEN** group 1 lists `src/app/constants.py` and the request adds that path again
- **THEN** `judge` returns `Refused` with the message `implement_amend_refused_path_status`

### Requirement: Refuse a rename form on add_path
The job MUST refuse an `add_path` request when `old` is given.

#### Scenario: Refuse an add_path request that gives old
- **WHEN** the request sets `kind` to `add_path` and `old` to `src/app/old.py`
- **THEN** `judge` returns `Refused` with the message `implement_amend_refused_path_status`
