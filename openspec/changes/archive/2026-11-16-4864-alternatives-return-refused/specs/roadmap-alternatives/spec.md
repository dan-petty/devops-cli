# roadmap-alternatives Specification

## Purpose
The check of `devops roadmap alternatives`: how refused replies are classified, reason codes recorded, and fixable replies sent back once.

## ADDED Requirements

### Requirement: Refusal reason code on the result line
The alternatives job SHALL write a stable reason code of a refused reply in the `reason` field of its result line.

#### Scenario: A refused reply names its reason code
- **WHEN** the job refuses a reply whose reason is the message `alternatives_reason_no_search`
- **THEN** the result line holds `result=refused` and `reason=no_search`

### Requirement: Last refusal code in the job record
The alternatives job SHALL keep the reason code of the last refused reply in the item's job record.

#### Scenario: A refusal writes its code beside the error class
- **WHEN** the job refuses a reply with the reason code `no_search`
- **THEN** the job record holds `alternatives.failed_reason=no_search` and keeps `alternatives.failed_error=RefusedReply`

### Requirement: One return for a fixable refusal
The alternatives job SHALL send a fixable refusal back to the model exactly once, with the reason, when the point's mode is `on`.

#### Scenario: A form refusal returns once and a valid reply records a verdict
- **WHEN** the mode of `alternatives.reply_fixable` is `on`, the reply is refused with the form code `no_tool`, and the job record holds no earlier refusal with that code
- **THEN** the rule gives the band `review`, `output_check` sends the reason back once, and a valid second reply records a verdict

### Requirement: No return for a repeated reason
The alternatives job MUST NOT send a refusal back when its reason code equals the code in the item's job record.

#### Scenario: The same reason code twice
- **WHEN** the reply is refused with a code that the item's job record already holds
- **THEN** the rule gives the band `continue`, the job makes no second model call and sets the next try 3 days later

### Requirement: 3-day wait for a not-fixable refusal
The alternatives job SHALL keep the 3-day wait for a refusal whose reason is not a schema or form error.

#### Scenario: A timeout reason waits 3 days
- **WHEN** the run stops on `UsageLimitExceeded`, or the reply is cut by the output limit
- **THEN** the code is not fixable, the rule gives the band `continue`, the job makes no second model call and sets the next try 3 days later

### Requirement: Return inside the attempt budget
The alternatives job MUST keep the one return inside the 10 searches and 30 fact reads of the attempt.

#### Scenario: The return stops at the budget
- **WHEN** the job makes the one return after a fixable refusal and the model calls `search_web` past the 10th search
- **THEN** the tool answers the call as text with no search, and the attempt reports at most 10 searches and 30 fact reads

### Requirement: Rule-only point with its table in the cuts file
The `alternatives.reply_fixable` point SHALL resolve with a rule and MUST read its fixable code table from its cuts file, not from a constant.

#### Scenario: The settings load accepts the point in shadow
- **WHEN** `roadmap.decisions` sets `alternatives.reply_fixable` to `shadow`
- **THEN** the settings load, and the cuts file of the point holds the fixable code table

### Requirement: Shadow mode records the band only
The `alternatives.reply_fixable` decision point SHALL run in mode `shadow` and record its band with no change to the job behavior.

#### Scenario: Shadow records a band and keeps the 3-day wait
- **WHEN** the mode of `alternatives.reply_fixable` is `shadow` and the reply is a fixable refusal
- **THEN** the result line holds the band `review` and the job makes no second model call and sets the next try 3 days later
