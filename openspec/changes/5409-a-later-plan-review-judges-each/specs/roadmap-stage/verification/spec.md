## RENAMED Requirements

- FROM: `### Requirement: One more repair round follows while the open findings drop`
- TO: `### Requirement: One more repair round follows while a review fixes more findings than it adds`

## MODIFIED Requirements

### Requirement: One more repair round follows while a review fixes more findings than it adds
After the last repair round of the setting, the stage SHALL start one more round only while the last review marked more earlier open findings `gone` than it opened new findings. The check SHALL read the verdicts of that one review, SHALL NOT compare the counts of two reviews, and SHALL make no model call. No item SHALL get more repair rounds than `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING`. No repair round SHALL start after the Service stops. Each round past the setting SHALL log the line `stage review extended:` with the round, the earlier findings that the last review fixed and the new open findings that it added.

#### Scenario: The open count drops after the last round
- **WHEN** the setting is 2, the first review opens 3 findings, the second review marks each of them `holds`, the third review marks one `gone` and opens no new finding, and the fourth review marks each finding `gone`
- **THEN** the planner gets 4 requests, the staged change holds no open finding, the job logs one `stage review extended:` line with `round=3 fixed=1 added=0`, and the result line counts 4 review runs

#### Scenario: The open count stays the same
- **WHEN** the setting is 2, the first review opens 3 findings, the second review marks one `gone`, and the third review marks one `gone` and opens 1 new finding in the changed text
- **THEN** the planner gets 3 requests, the staged change holds 2 open findings, and the job logs no `stage review extended:` line

#### Scenario: No round past the ceiling
- **WHEN** the setting is 2 and each later review marks one earlier finding `gone` and opens no new finding
- **THEN** the planner gets 1 + `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` requests

#### Scenario: No round in a drain
- **WHEN** the Service stops during the first review, and the review returns the plan
- **THEN** no repair round starts, the planner gets 1 request, and the item ends with the stop

## ADDED Requirements

### Requirement: A later review gets the earlier open findings and the answer
A review that follows a repair SHALL get, beside the issue, the plan and the files, the key `earlier`, which holds each open finding of the review before it with its `number`, `type`, `where`, `problem` and `quote`, and the key `answer`, which holds each block of lines of the plan that the revision added or changed. The task prompt `roadmap_stage_verify_later.md` SHALL follow the prompt of the pass in such a review.

#### Scenario: The request of a repair round
- **WHEN** the first review opens a `false_premise` finding, and the planner answers a revision that changes the `why` of the plan
- **THEN** the second request of the verifier holds the finding in `earlier` with the number 1, and `answer` holds the new `why`

### Requirement: A later review gives a verdict for each earlier finding
The reply of a later review SHALL give one verdict, `holds` or `gone`, for each earlier finding, and the new findings. An earlier finding that the reply marks `holds`, gives no verdict, or reports again as a new finding SHALL stay open. Any other earlier finding that it marks `gone` SHALL be fixed.

#### Scenario: A verdict closes a finding
- **WHEN** the first review opens one finding and the review of the revision marks it `gone` and opens no new finding
- **THEN** the staged change holds no open finding

#### Scenario: No verdict keeps a finding
- **WHEN** the first review opens two findings and the review of the revision gives a verdict only for the first, `gone`
- **THEN** the second finding stays open

### Requirement: The first review of a plan keeps its request
The first review of a plan SHALL get no `earlier` and no `answer` key, the reply schema with only `findings`, and the prompt of the pass with no text of a later review. So the golden set of `devops roadmap eval verify`, which scores a first review, keeps its request.

#### Scenario: The first review does not change
- **WHEN** the first review of a plan sends its request
- **THEN** the request holds only `number`, `title`, `body`, `plan` and `files`, and the instructions are the prompt of the pass and the rules of the tools

### Requirement: A later review opens a new finding only in changed text
A new finding of a later review SHALL be open only when it is open by the rules of an open finding and its quote, with white space folded, is in a block of `answer`. A new finding on a text that the revision did not change SHALL be advice, which the comment lists. The step SHALL take the blocks of `answer` from a `difflib` diff of the lines of the plan before the repair and of the revision, so a line that the revision moves is changed text.

#### Scenario: A new finding on unchanged text
- **WHEN** a later review opens a `false_premise` finding whose quote is in the issue, and the revision did not change that text
- **THEN** the finding is advice, and it returns no plan

#### Scenario: A new finding on changed text
- **WHEN** a later review opens a `false_premise` finding whose quote is in a line of the plan that the revision added
- **THEN** the finding is open
