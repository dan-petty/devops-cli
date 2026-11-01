## ADDED Requirements

### Requirement: The refine reply can defer a part of the item
The refine reply SHALL accept the key `deferred`: a list of at most 3 parts, each with a non-empty `title` and a non-empty `body`. The key SHALL default to an empty list. The reply SHALL be refused when a part has another key, when a part has an empty `title` or `body`, or when the list holds more than 3 parts.

#### Scenario: A reply with two parts
- **WHEN** a reply gives `deferred` with two parts, each with a title and a body
- **THEN** the proposal holds both parts in order

#### Scenario: A reply with four parts
- **WHEN** a reply gives `deferred` with four parts
- **THEN** the reply fails validation

#### Scenario: A reply without the key
- **WHEN** a reply gives no `deferred`
- **THEN** the proposal holds no part, and the round behaves as it did before

### Requirement: A deferred part does not block Ready
Refine SHALL decide `is_ready` on the proposal without its deferred parts. `fits_one_pr`, `split_offs` and `NextStep.SPLIT` SHALL keep their meaning for an item that is too big for one pull request.

#### Scenario: A complete proposal with a deferred part
- **WHEN** the proposal has a problem statement, a complete criterion, an existing-tool answer, no open question, no block, `fits_one_pr` true and one deferred part
- **THEN** the planned item is Ready and its next step is `ready`

#### Scenario: A proposal that is too big
- **WHEN** the proposal has `fits_one_pr` false and two `split_offs`
- **THEN** the next step is `split` and the item is not Ready

### Requirement: Refine files each deferred part through intake when it sets the item Ready
When refine plans an item Ready with deferred parts, it SHALL make one intake plan for each part, with a candidate that has no `source`, and `--confirm` SHALL file the parts through intake before refine writes the section or the status. The body of each new issue SHALL start with `Split from #<issue>.`. Refine SHALL file no part for an item that is not Ready. Refine SHALL set the Status of a new issue and its Priority through intake only, and SHALL set no milestone.

#### Scenario: Two parts on a Ready item
- **WHEN** a round with `--confirm` refines a New item whose proposal is complete and holds two deferred parts, and intake places both
- **THEN** two issues exist with the part titles, their bodies start with `Split from #<issue>.`, and the item is Ready

#### Scenario: An item that stays New
- **WHEN** the proposal holds an open question and one deferred part
- **THEN** refine files no issue, and the item stays New with the next step `person`

#### Scenario: A plan without `--confirm`
- **WHEN** a round plans an item with a deferred part and does not confirm
- **THEN** the plan holds the intake plan of the part and the store holds no new issue

### Requirement: A deferred part is linked by a body line, a comment and a record
Refine SHALL NOT link a deferred part as a sub-issue of the item. After it files the parts, refine SHALL add one sentence that names each new issue number to the Ready comment of the item, SHALL NOT post another comment, and SHALL record the numbers, comma separated, as `refine.deferred` in the job record.

#### Scenario: The links of two parts
- **WHEN** refine files two parts of item 7 as issues 21 and 22
- **THEN** the Ready comment of item 7 names `#21` and `#22`, the job record of item 7 holds `refine.deferred` `21,22`, and item 7 has no sub-issue

### Requirement: A part that intake cannot place keeps the item New
When the intake plan of a deferred part has no placement, or the text of the part is refused as a secret, refine SHALL NOT set the item Ready, SHALL file no part of the item, and SHALL give the item the next step `person` with a detail that names the part.

#### Scenario: Intake skips a part
- **WHEN** a complete proposal holds a deferred part and the intake model gives no usable proposal for it
- **THEN** the item stays New, the next step is `person`, its detail names the part title, and no issue is filed

### Requirement: A deferred part is filed once
The request to the proposal model SHALL carry `deferred_issues`: the number and title of each issue in the `refine.deferred` record of the item. Refine SHALL drop a deferred part whose title equals, with the white space joined, the title of a recorded issue. When a round files only some parts, refine SHALL record their numbers, SHALL write no section and no status, and SHALL log a warning that names the item.

#### Scenario: A part filed in an earlier round
- **WHEN** the job record holds `refine.deferred` `21` for an item, issue 21 has the title `Decide the storage` and the model defers a part with that title again
- **THEN** the intake plan holds no candidate for it and the request held `deferred_issues` with issue 21

#### Scenario: A write fails for the second part
- **WHEN** the store refuses the creation of the second of two parts
- **THEN** the job record holds the number of the first issue as `refine.deferred`, the body and Status of the item are as they were, and a warning names the item

### Requirement: The dry run lists the requests of a deferred part
`devops roadmap refine --dry-run` SHALL list the requests of one intake candidate, with the condition that the proposal defers a part, in the plan of a round and in the plan of `--item`. It SHALL make no request.

#### Scenario: The plan of an item
- **WHEN** the plan of `devops roadmap refine --item 7 --dry-run` is built
- **THEN** its requests hold the creation of an issue with the condition "the proposal defers a part of the item", and no request was sent
