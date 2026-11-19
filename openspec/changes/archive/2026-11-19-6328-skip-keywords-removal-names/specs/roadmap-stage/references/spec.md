## ADDED Requirements

### Requirement: A Python keyword is never a removed name
`find_removed_names` SHALL skip a backticked span that is a Python hard keyword (`keyword.iskeyword`) or a Python soft keyword (`keyword.issoftkeyword`), in the active and in the passive removal form. It SHALL keep each other span that is a Python identifier. A plan whose only removed span is a keyword SHALL give no unhandled reference.

#### Scenario: A plan drops a hard keyword
- **WHEN** `find_removed_names` receives the text "The change drops `and` from the title."
- **THEN** it returns an empty set

#### Scenario: A plan drops a soft keyword
- **WHEN** `find_removed_names` receives the text "The change drops `match` from the title."
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
