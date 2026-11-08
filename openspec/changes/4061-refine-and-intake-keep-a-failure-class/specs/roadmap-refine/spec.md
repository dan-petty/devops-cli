## ADDED Requirements

### Requirement: A failed model call records its class and waits
When the model call of an item fails, refine SHALL record `refine.failed_at`, `refine.failed_step` (`investigate`) and `refine.failed_class` (the class of the error) in the job record, in the same marks write as the failed body hash when the item's text caused the failure. A placeholder failure SHALL record nothing. A round without `--item` SHALL leave the item out until `refine.failed_at` plus the wait of its class, and SHALL take the other items.

#### Scenario: A timeout
- **WHEN** the gateway answers an item with a timeout
- **THEN** the job record holds the time, the step `investigate` and the class `provider`, it holds no failed body hash, and one marks write made them

#### Scenario: The wait has not passed
- **WHEN** the next round runs 59 minutes after a `provider` failure
- **THEN** it sends no request for the item, lists it as waiting with the step `retry`, and refines the other items

#### Scenario: The wait has passed
- **WHEN** the next round runs 1 hour after a `provider` failure
- **THEN** the round takes the item again

#### Scenario: A reply that never validates
- **WHEN** a reply never validates, and the round runs 5 hours 59 minutes later and then 6 hours later
- **THEN** the job record holds the class `parser` and the failed body hash from one write, the first round sends no request, and the second takes the item

#### Scenario: A record with no usable class
- **WHEN** the job record holds `refine.failed_at` and no class, or a class that is no failure class, or a class with no wait
- **THEN** the item waits as `ci_infra`, and a time that is no time holds the item for no time

#### Scenario: A person overrules the wait
- **WHEN** a person runs refine with `--item` for an item that waits
- **THEN** the round refines the item

#### Scenario: A body edit
- **WHEN** a person edits the body of an item after a failure that its text caused
- **THEN** the next round takes the item

#### Scenario: The second failure on the same body
- **WHEN** a second reply on the same body never validates
- **THEN** the item waits on a body edit and the three keys are cleared

### Requirement: A round whose model call worked clears the failed class
A round whose model call worked SHALL clear `refine.failed_at`, `refine.failed_step` and `refine.failed_class` from the job record, whether the round refined the item or ended in a job failure.

#### Scenario: A success after a timeout
- **WHEN** a round refines an item whose record holds the three keys
- **THEN** the record holds none of them

#### Scenario: A form check fails after a timeout
- **WHEN** a round gets a proposal that fails a form check for an item whose record holds the three keys
- **THEN** the record holds `refine.tries` and none of the three keys
