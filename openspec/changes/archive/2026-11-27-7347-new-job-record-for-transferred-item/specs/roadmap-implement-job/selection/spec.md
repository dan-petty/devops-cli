## ADDED Requirements

### Requirement: A recorded draft is the draft of an item only on the branch of the item
The selection of the implement job SHALL take the pull request that the record of a Staged item names as the draft of the item only when the head branch of that pull request is the recorded branch of the item. For any other head branch it SHALL leave the item out with the reason of a pull request that is no open draft.

#### Scenario: An open draft on another branch
- **WHEN** the record of a Staged item names the branch `fix/1-the-job-drops-a-comment` and an open draft whose head branch is `feat/4107-add-the-rows`
- **THEN** the selection takes no item, and the reason of the item is `Its pull request #<n> is not an open draft.`
