## ADDED Requirements

### Requirement: The model reads the reason of a rejected plan
The comment of a rejected plan SHALL be a comment of the stage job. It SHALL stay out of `replies`, and `stage_return` SHALL hold its reason, without the marker of the stage job and without the marker of a rejected plan. Refine SHALL give the item one new look after the comment, as it does after any other return of the stage job.

#### Scenario: The request after a rejected plan
- **WHEN** the stage job commented the reason of a rejected plan and returned the item to New, and refine looks at the item
- **THEN** `stage_return` holds the reason, holds no marker, and `replies` is empty

### Requirement: The prompts of refine name the reason of a rejected plan
The prompts of the proposal and of the investigation SHALL say that the reason in `stage_return` can be the reason of a person who rejected a plan, and that the item must not become Ready again with the same proposal.

#### Scenario: The prompts name the case
- **WHEN** a test reads the two prompts
- **THEN** each one names `stage_return` and a rejected plan
