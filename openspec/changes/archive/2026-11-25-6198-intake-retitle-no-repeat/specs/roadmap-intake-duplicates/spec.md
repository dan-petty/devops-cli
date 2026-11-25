## ADDED Requirements

### Requirement: Refine deferrals carry an apart set
`NewCandidate` SHALL accept an `apart` collection of issue numbers that `_apart` excludes from the duplicate shortlist, and refine deferrals SHALL populate `apart` with the parent issue number and the numbers in `refine.deferred`.

#### Scenario: NewCandidate apart excludes an issue without a source
- **WHEN** intake plans a `NewCandidate` with `apart={6167}` and no `source`
- **THEN** the shortlist sent to the intake model excludes issue `#6167`

#### Scenario: Refine deferral excludes parent and recorded deferrals
- **WHEN** refine plans a deferred part for an item with recorded `refine.deferred` numbers
- **THEN** intake excludes both the parent issue and the recorded deferred issues from the candidate shortlist
