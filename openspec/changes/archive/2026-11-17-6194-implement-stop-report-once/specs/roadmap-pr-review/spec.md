## ADDED Requirements

### Requirement: A discard of a rule writes its verdict on the issue
A discard of a rule SHALL write the verdict, its reason and its evidence in the return comment on the issue, which the jobs and refine read. After that comment, the comment of the step on the pull request SHALL become the line "The review discarded this pull request. The verdict is on #<issue>: <url>." with the page of the return comment. A call that ends a discard on the closed pull request SHALL leave the comment of the pull request as it is.

#### Scenario: A discarded delivery
- **WHEN** the verdict of a delivery is a discard implementation of a rule with a reason and one line of evidence
- **THEN** the return comment on the issue holds the reason and the evidence, and the comment of the step on the pull request holds the page of that comment and not the reason
