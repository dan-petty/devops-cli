## MODIFIED Requirements

### Requirement: removed names come from a removal verb
The scan SHALL take each backticked identifier that a removal verb (`remove`, `delete`, `deprecate`, or `retire`, in active or passive form) governs in `proposal.md` or `design.md` as a removed name, and SHALL NOT treat `drop`, `drops`, `dropped`, or `dropping` as a removal verb.

#### Scenario: a removal sentence names two identifiers
- **WHEN** a fixture `proposal.md` holds the sentence `removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE``
- **THEN** the scan searches for `valkey_set` and does not search for `CONST_MCP_EXPOSURE_TABLE`.

#### Scenario: a plan drops a step before a code span
- **WHEN** the plan text reads `The plan dropped the `rewrite` step.` or `Another item drops `tool_a` from `registry`.`
- **THEN** `find_removed_names` returns an empty set.

#### Scenario: a dropped step gives no removal-reference finding
- **WHEN** the proposal reads `The plan dropped the `rewrite` step.` and `tests/example_test.py` holds `rewrite`
- **THEN** `scan_removal_references` returns `unhandled_tests == {}` and `has_test_failures is False`.

#### Scenario: a deleted function still gets a finding
- **WHEN** the proposal reads `The change deletes `valkey_set`.` and `tests/example_test.py` calls `valkey_set`
- **THEN** `scan_removal_references` returns `unhandled_tests == {"valkey_set": ["tests/example_test.py"]}`.

### Requirement: A Python keyword is never a removed name
`find_removed_names` SHALL skip a backticked span that is a Python hard keyword (`keyword.iskeyword`) or a Python soft keyword (`keyword.issoftkeyword`), in the active and in the passive removal form. It SHALL keep each other span that is a Python identifier. A plan whose only removed span is a keyword SHALL give no unhandled reference.

#### Scenario: A plan drops a hard keyword
- **WHEN** `find_removed_names` receives the text "The change drops `and` from the title."
- **THEN** it returns an empty set

#### Scenario: A plan drops a soft keyword
- **WHEN** `find_removed_names` receives the text "The change drops `match` from the title."
- **THEN** it returns an empty set

#### Scenario: A plan removes a hard keyword
- **WHEN** `find_removed_names` receives the text "The change removes `and` from the title."
- **THEN** it returns an empty set

#### Scenario: A plan removes a soft keyword
- **WHEN** `find_removed_names` receives the text "The change removes `match` from the title."
- **THEN** it returns an empty set

#### Scenario: A plan says that a keyword is removed
- **WHEN** `find_removed_names` receives the text "`and` is removed from the title."
- **THEN** it returns an empty set

#### Scenario: A plan removes an ordinary identifier
- **WHEN** `find_removed_names` receives the text "The change removes `old_helper`."
- **THEN** it returns `{"old_helper"}`

#### Scenario: A change folder drops a keyword
- **WHEN** `scan_removal_references` runs on a change whose `proposal.md` says "drops `and` from the title" and on a repository whose test file contains `and`
- **THEN** `has_test_failures` is false and `unhandled_tests` is empty

#### Scenario: A change folder removes a keyword
- **WHEN** `scan_removal_references` runs on a change whose `proposal.md` says "removes `and` from the title" and on a repository whose test file contains `and`
- **THEN** `has_test_failures` is false and `unhandled_tests` is empty
