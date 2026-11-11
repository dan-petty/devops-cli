## ADDED Requirements

### Requirement: One conflict judgment
`devops pr check-readiness`, the implement watch and the Service row `pr_conflicts` SHALL judge a merge conflict with the one function `merge_conflict`. It SHALL return True when `mergeable` is false or the state is `dirty` or `conflicting`, None when `mergeable` is null or the state is `unknown` or empty, and False else.

#### Scenario: The row and check-readiness on one pull request
- **WHEN** the pull request payload holds `mergeable` false with `mergeable_state` `dirty`
- **THEN** `merge_conflict` reports a conflict and the row posts the conflict comment

#### Scenario: A pull request that is only behind
- **WHEN** the pull request payload holds `mergeable` true with `mergeable_state` `behind`
- **THEN** `merge_conflict` reports no conflict and the row posts no comment

#### Scenario: A state that GitHub has not computed
- **WHEN** the pull request payload holds `mergeable` null with `mergeable_state` `unknown`
- **THEN** `merge_conflict` returns None and the row posts no comment
